import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

# Activities
from src.workers.polecat_activities import polecat_developer_activity

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("PolecatWorker")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        logger.info(f"🐾 Polecat Worker: Connected to Temporal at {temporal_address}")
    except Exception as e:
        logger.error(f"🐾 Polecat Worker: Failed to connect to Temporal: {e}")
        return

    # The Polecat Worker handles the isolated Git worktrees and implementation
    target_queue = os.getenv("POLECAT_QUEUE", "betting-app-queue")
    worker = Worker(
        client,
        task_queue=target_queue,
        activities=[polecat_developer_activity],
        workflow_runner=UnsandboxedWorkflowRunner(),
        max_concurrent_activities=10
    )

    logger.info(f"🐾 POLECAT WORKER STARTED (Polling {target_queue})")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
