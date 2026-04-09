import asyncio
import os
import logging
import signal
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio import activity

# Workflow Imports
from src.workers.pipeline_workflow import *
from src.workers.mayor_workflow import *
from src.workers.design_workflow import DesignWorkflow
from src.workers.breakdown_workflow import BreakdownWorkflow
from src.workers.implementation_workflow import ImplementationWorkflow
from src.workers.refinery_workflow import *
from src.workers.nexus_security import (
    SecurityAuditServiceHandler, SecurityAuditWorkflow, 
    run_security_scans_activity
)
from src.workers.polecat_activities import polecat_developer_activity
import scripts.beads_manager as beads_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedOrchestrator")

async def run_worker_with_restart(name, worker_coro):
    while True:
        try:
            logger.info(f"🚀 Starting {name}...")
            await worker_coro()
        except Exception as e:
            logger.error(f"💀 {name} CRASHED: {e}. Restarting in 5s...")
            await asyncio.sleep(5)

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-type", choices=["orchestrator", "developer", "homelab", "all"], default="all")
    parser.add_argument("--namespace", default="default")
    args = parser.parse_args()

    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = args.namespace
    
    logger.info(f"🌐 GASTOWN WORKER: Type={args.worker_type} | Namespace={temporal_namespace}")
    
    client = await Client.connect(temporal_address, namespace=temporal_namespace)
    workers = []

    # All Capabilities
    all_workflows = [
        MayorWorkflow, MasterPipelineWorkflow, RefineryWorkflow,
        DesignWorkflow, BreakdownWorkflow, ImplementationWorkflow,
        SecurityAuditWorkflow
    ]
    
    all_activities = [
        system_integrity_check_activity,
        discovery_activity, check_changes_activity, build_activity, test_activity,
        secure_activity, deploy_activity, create_sre_bug_activity,
        triage_task_queue, ba_design_activity, architect_design_activity,
        game_designer_activity, domain_experts_activity, quarterback_synthesis_activity,
        design_refine_activity,
        breakdown_activity, mark_breakdown_started_activity, get_task_title_activity,
        get_bead_context_activity,
        clear_breakdown_marker_activity,
        move_task_activity, post_comment_activity,
        check_epic_completion_activity,
        data_integrity_audit_activity,
        playwright_e2e_audit_activity,
        pre_commit_audit_activity,
        refine_and_merge_activity,
        cleanup_refinery_activity,
        broadcast_status_activity,
        run_security_scans_activity
    ]

    from src.utils.namespace_manager import NamespaceManager
    target_queue = NamespaceManager.get_queue_for_namespace(temporal_namespace)

    # Throttled Activity Logic
    llm_lock = asyncio.Lock()
    @activity.defn(name="polecat_developer_activity")
    async def polecat_developer_activity_throttled(bead_id: str) -> str:
        async with llm_lock:
            return await polecat_developer_activity(bead_id)

    # SRE: The Single Resilient Worker
    # In each namespace, we start ONE worker that polls the namespace's primary queue.
    # This worker handles BOTH workflows and activities.
    worker = Worker(
        client,
        task_queue=target_queue,
        workflows=all_workflows,
        activities=all_activities + [polecat_developer_activity_throttled],
        nexus_service_handlers=[SecurityAuditServiceHandler()],
        workflow_runner=UnsandboxedWorkflowRunner()
    )
    workers.append(run_worker_with_restart(f"Worker-{temporal_namespace}", worker.run))

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except: pass

    await asyncio.gather(*workers)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
