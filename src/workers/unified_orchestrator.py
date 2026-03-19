import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio import activity

# Workflows
from src.workers.pipeline_workflow import MasterPipelineWorkflow
from src.workers.mayor_workflow import MayorWorkflow
from src.workers.refinery_workflow import RefineryWorkflow

# Pipeline activities
from src.workers.pipeline_workflow import (
    discovery_activity,
    check_changes_activity,
    build_activity,
    test_activity,
    secure_activity,
    deploy_activity,
    create_sre_bug_activity
)

# Mayor activities
from src.workers.mayor_workflow import (
    triage_task_queue,
    ba_design_activity,
    architect_design_activity,
    game_designer_activity,
    domain_experts_activity,
    quarterback_synthesis_activity,
    design_refine_activity,
    breakdown_activity,
    get_task_title_activity,
    move_task_activity,
    post_comment_activity,
    check_epic_completion_activity,
    mark_breakdown_started_activity,
    clear_breakdown_marker_activity,
)

# Refinery activities
from src.workers.refinery_workflow import (
    refine_and_merge_activity,
    lint_and_format_activity,
    integration_test_activity,
    rollback_merge_activity,
    cleanup_refinery_activity,
    create_gate_failure_bug_activity,
    broadcast_status_activity,
)

# Polecat developer activity
from src.workers.polecat_activities import polecat_developer_activity


async def main():
    logging.basicConfig(level=logging.INFO)

    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)

    # --- SHARED AGENT LOGIC ---
    from src.agents.architect import ArchitectAgent
    from src.agents.sre import SREAgent
    from beads_manager import update_bead, read_bead, add_comment

    @activity.defn
    async def architect_activity(bead_id: str) -> str:
        agent = ArchitectAgent()
        bead_data = read_bead(bead_id)
        result = await agent.analyze(
            bead_data.get("title", ""),
            bead_data.get("description", ""),
            "Migrated to Unified Orchestrator"
        )
        update_bead(bead_id, {
            "description": result.get("updated_description"),
            "status": "designing"
        })
        return "Architect execution success"

    @activity.defn
    async def sre_activity(bead_id: str) -> str:
        agent = SREAgent()
        bead_data = read_bead(bead_id)
        diagnosis = await agent.diagnose(bead_data.get("title", ""), bead_data.get("description", ""))
        update_bead(bead_id, {"resolution": diagnosis.get("diagnosis"), "status": "resolved"})
        return "SRE execution success"

    # 1. Main Orchestrator Worker (Mayor + SDLC Pipeline + Refinery)
    orchestrator_worker = Worker(
        client,
        task_queue="main-orchestrator-queue",
        workflows=[MayorWorkflow, MasterPipelineWorkflow, RefineryWorkflow],
        activities=[
            # Mayor
            triage_task_queue,
            ba_design_activity,
            architect_design_activity,
            game_designer_activity,
            domain_experts_activity,
            quarterback_synthesis_activity,
            design_refine_activity,
            breakdown_activity,
            get_task_title_activity,
            move_task_activity,
            post_comment_activity,
            check_epic_completion_activity,
            mark_breakdown_started_activity,
            clear_breakdown_marker_activity,
            # Pipeline
            discovery_activity,
            check_changes_activity,
            build_activity,
            test_activity,
            secure_activity,
            deploy_activity,
            create_sre_bug_activity,
            # Refinery
            refine_and_merge_activity,
            lint_and_format_activity,
            integration_test_activity,
            rollback_merge_activity,
            cleanup_refinery_activity,
            create_gate_failure_bug_activity,
            broadcast_status_activity,
            # Shared agents
            architect_activity,
            sre_activity,
        ],
        workflow_runner=UnsandboxedWorkflowRunner()
    )

    # 2. Architect Queue Worker
    architect_worker = Worker(
        client,
        task_queue="architect-queue",
        activities=[architect_activity],
    )

    # 3. SRE Queue Worker
    sre_worker = Worker(
        client,
        task_queue="sre-queue",
        activities=[sre_activity, polecat_developer_activity],
    )

    # 4. Betting App Polecat Developer Queue
    developer_worker = Worker(
        client,
        task_queue="betting-app-queue",
        activities=[polecat_developer_activity],
    )

    # 5. Homelab Polecat Developer Queue
    homelab_worker = Worker(
        client,
        task_queue="homelab-queue",
        activities=[polecat_developer_activity],
    )

    print("🤖 UNIFIED BESTFAM ORCHESTRATOR (GASTOWN MODE) STARTED")
    print(f"Connecting to Temporal at: {temporal_address}")

    # Run all workers concurrently
    await asyncio.gather(
        orchestrator_worker.run(),
        architect_worker.run(),
        sre_worker.run(),
        developer_worker.run(),
        homelab_worker.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
