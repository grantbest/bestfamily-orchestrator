import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

# Workflows
from src.workers.refinery_workflow import RefineryWorkflow

# Activities
from src.workers.refinery_workflow import (
    refine_and_merge_activity, 
    lint_and_format_activity,
    integration_test_activity,
    rollback_merge_activity,
    cleanup_refinery_activity,
    create_gate_failure_bug_activity,
    broadcast_status_activity
)

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("RefineryWorker")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        logger.info(f"🏗️ Refinery Worker: Connected to Temporal at {temporal_address}")
    except Exception as e:
        logger.error(f"🏗️ Refinery Worker: Failed to connect to Temporal: {e}")
        return

    # The Refinery Worker handles merging and validation
    worker = Worker(
        client,
        task_queue="refinery-queue", # Refinery listens on its own dedicated queue
        workflows=[RefineryWorkflow],
        activities=[
            refine_and_merge_activity, 
            lint_and_format_activity,
            integration_test_activity,
            rollback_merge_activity,
            cleanup_refinery_activity,
            create_gate_failure_bug_activity,
            broadcast_status_activity
        ],
        workflow_runner=UnsandboxedWorkflowRunner(),
        max_concurrent_activities=10
    )

    logger.info("🏗️ REFINERY WORKER STARTED (Polling refinery-queue)")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
