import asyncio
import os
import logging
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
    lint_and_format_activity, check_evidence_activity, broadcast_status_activity
)

from src.workers.polecat_activities import polecat_developer_activity

import beads_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedOrchestrator")

async def main():
    print(f"📦 BEADS_MANAGER VERSION: {beads_manager.VERSION}")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)

    orchestrator_worker = Worker(
        client,
        task_queue="modular-orchestrator-queue",
        workflows=[
            MayorWorkflow, MasterPipelineWorkflow, RefineryWorkflow,
            DesignWorkflow, BreakdownWorkflow, ImplementationWorkflow
        ],
        activities=[
            discovery_activity, check_changes_activity, build_activity, test_activity,
            secure_activity, deploy_activity, create_sre_bug_activity,
            triage_task_queue, ba_design_activity, architect_design_activity,
            game_designer_activity, domain_experts_activity, quarterback_synthesis_activity,
            breakdown_activity, mark_breakdown_started_activity, get_task_title_activity,
            move_task_activity, check_epic_completion_activity,
            lint_and_format_activity, check_evidence_activity, broadcast_status_activity
        ],
        workflow_runner=UnsandboxedWorkflowRunner()
    )

    developer_worker = Worker(client, task_queue="betting-app-queue", activities=[polecat_developer_activity])
    homelab_worker = Worker(client, task_queue="homelab-queue", activities=[polecat_developer_activity])

    print("🤖 UNIFIED BESTFAM ORCHESTRATOR STARTED")
    await asyncio.gather(
        orchestrator_worker.run(),
        developer_worker.run(),
        homelab_worker.run(),
    )

if __name__ == "__main__":
    asyncio.run(main())
