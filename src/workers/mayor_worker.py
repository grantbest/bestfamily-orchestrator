import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

# Workflows
from src.workers.mayor_workflow import MayorWorkflow

# Activities
from src.workers.mayor_workflow import (
    triage_task_queue,
    ba_design_activity,
    architect_design_activity,
    game_designer_activity,
    domain_experts_activity,
    quarterback_synthesis_activity,
    breakdown_activity
)

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("MayorWorker")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        logger.info(f"🏛️ Mayor Worker: Connected to Temporal at {temporal_address}")
    except Exception as e:
        logger.error(f"🏛️ Mayor Worker: Failed to connect to Temporal: {e}")
        return

    # The Mayor Worker only handles the high-level Triage and Coordination
    worker = Worker(
        client,
        task_queue="main-orchestrator-queue",
        workflows=[MayorWorkflow],
        activities=[
            triage_task_queue,
            ba_design_activity,
            architect_design_activity,
            game_designer_activity,
            domain_experts_activity,
            quarterback_synthesis_activity,
            breakdown_activity
        ],
        workflow_runner=UnsandboxedWorkflowRunner()
    )

    logger.info("🏛️ MAYOR WORKER STARTED (Polling main-orchestrator-queue)")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
