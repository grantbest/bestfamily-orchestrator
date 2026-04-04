import asyncio
import os
import logging
import signal
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio import activity

from src.workers.pipeline_workflow import MasterPipelineWorkflow
from src.workers.mayor_workflow import MayorWorkflow
from src.workers.refinery_workflow import RefineryWorkflow
from src.workers.design_workflow import DesignWorkflow
from src.workers.breakdown_workflow import BreakdownWorkflow
from src.workers.implementation_workflow import ImplementationWorkflow

from src.workers.pipeline_workflow import (
    discovery_activity, check_changes_activity, build_activity, test_activity,
    secure_activity, deploy_activity, create_sre_bug_activity
)

from src.workers.mayor_workflow import (
    triage_task_queue, ba_design_activity, architect_design_activity,
    game_designer_activity, domain_experts_activity, quarterback_synthesis_activity,
    breakdown_activity, mark_breakdown_started_activity, get_task_title_activity,
    move_task_activity, check_epic_completion_activity
)

from src.workers.refinery_workflow import (
    resolve_refinery_strategy_activity,
    lint_and_format_activity, check_evidence_activity, 
    refine_and_merge_activity, cleanup_refinery_activity,
    broadcast_status_activity, read_bead_activity,
    integration_test_activity, rollback_merge_activity,
    create_gate_failure_bug_activity, synthetic_health_check_activity
)

from src.workers.nexus_security import (
    SecurityAuditServiceHandler, SecurityAuditWorkflow, 
    run_security_scans_activity
)

from src.workers.polecat_activities import polecat_developer_activity

import beads_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedOrchestrator")

# --- Bug 1: Supervisor/Daemon Pattern ---

async def run_worker_with_restart(name, worker_coro):
    """Supervises a worker and restarts it on failure."""
    while True:
        try:
            logger.info(f"🚀 Starting {name}...")
            await worker_coro()
        except Exception as e:
            logger.error(f"💀 {name} CRASHED: {e}. Restarting in 5s...")
            await asyncio.sleep(5)

async def main():
    print(f"📦 BEADS_MANAGER VERSION: {beads_manager.VERSION}")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "gastown")
    
    # Bug 8: Connection resilience
    max_retries = 5
    for i in range(max_retries):
        try:
            client = await Client.connect(temporal_address, namespace=temporal_namespace)
            break
        except Exception as e:
            if i == max_retries - 1: raise
            logger.warning(f"Failed to connect to Temporal at {temporal_address}: {e}. Retrying {i+1}/{max_retries}...")
            await asyncio.sleep(2)

    orchestrator_worker = Worker(
        client,
        task_queue="modular-orchestrator-queue",
        workflows=[
            MayorWorkflow, MasterPipelineWorkflow, RefineryWorkflow,
            DesignWorkflow, BreakdownWorkflow, ImplementationWorkflow,
            SecurityAuditWorkflow
        ],
        activities=[
            discovery_activity, check_changes_activity, build_activity, test_activity,
            secure_activity, deploy_activity, create_sre_bug_activity,
            triage_task_queue, ba_design_activity, architect_design_activity,
            game_designer_activity, domain_experts_activity, quarterback_synthesis_activity,
            breakdown_activity, mark_breakdown_started_activity, get_task_title_activity,
            move_task_activity, check_epic_completion_activity,
            resolve_refinery_strategy_activity,
            lint_and_format_activity, check_evidence_activity, 
            refine_and_merge_activity, cleanup_refinery_activity,
            broadcast_status_activity, read_bead_activity,
            run_security_scans_activity,
            integration_test_activity, rollback_merge_activity,
            create_gate_failure_bug_activity, synthetic_health_check_activity
        ],
        nexus_service_handlers=[SecurityAuditServiceHandler()],
        workflow_runner=UnsandboxedWorkflowRunner()
    )

    developer_worker = Worker(client, task_queue="betting-app-queue", activities=[polecat_developer_activity])
    homelab_worker = Worker(client, task_queue="homelab-queue", activities=[polecat_developer_activity])

    logger.info("🤖 UNIFIED BESTFAM ORCHESTRATOR STARTED WITH SUPERVISOR")

    # Handle graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop_event.set())

    # Supervise workers
    workers = [
        run_worker_with_restart("OrchestratorWorker", orchestrator_worker.run),
        run_worker_with_restart("DeveloperWorker", developer_worker.run),
        run_worker_with_restart("HomelabWorker", homelab_worker.run),
    ]

    worker_task = asyncio.gather(*workers)
    
    # Wait for stop event
    await stop_event.wait()
    logger.info("🛑 Shutting down orchestrator...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
