import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio import activity

# Workflows
from src.workers.pipeline_workflow import MasterPipelineWorkflow
from src.workers.triage_workflow import TriageWorkflow

# Activities
from src.workers.pipeline_workflow import (
    discovery_activity,
    build_activity,
    test_activity,
    secure_activity,
    deploy_activity,
    create_sre_bug_activity
)
from src.workers.triage_workflow import triage_task_queue

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

    # 1. Main Orchestrator Worker (Triage + SDLC Pipeline)
    orchestrator_worker = Worker(
        client,
        task_queue="main-orchestrator-queue",
        workflows=[TriageWorkflow, MasterPipelineWorkflow],
        activities=[
            triage_task_queue,
            discovery_activity,
            build_activity,
            test_activity,
            secure_activity,
            deploy_activity,
            create_sre_bug_activity,
            architect_activity, # Shared
            sre_activity        # Shared
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
        activities=[sre_activity],
    )

    print("🤖 UNIFIED BESTFAM ORCHESTRATOR STARTED")
    print(f"Connecting to Temporal at: {temporal_address}")
    
    # Run all workers concurrently
    await asyncio.gather(
        orchestrator_worker.run(),
        architect_worker.run(),
        sre_worker.run()
    )

if __name__ == "__main__":
    asyncio.run(main())
