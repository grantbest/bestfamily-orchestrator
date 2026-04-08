import asyncio
import os
import sys
import logging

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

# Workflows
from src.workers.pipeline_workflow import MasterPipelineWorkflow

# Activities
from src.workers.pipeline_workflow import (
    discovery_activity, 
    check_changes_activity, 
    build_activity, 
    test_activity,
    secure_activity, 
    deploy_activity, 
    create_sre_bug_activity
)

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("PipelineWorker")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        logger.info(f"🏗️ Pipeline Worker: Connected to Temporal at {temporal_address}")
    except Exception as e:
        logger.error(f"🏗️ Pipeline Worker: Failed to connect to Temporal: {e}")
        return

    worker = Worker(
        client,
        task_queue="modular-orchestrator-queue",
        workflows=[MasterPipelineWorkflow],
        activities=[
            discovery_activity, 
            check_changes_activity, 
            build_activity, 
            test_activity,
            secure_activity, 
            deploy_activity, 
            create_sre_bug_activity
        ],
        workflow_runner=UnsandboxedWorkflowRunner()
    )

    logger.info("🏗️ PIPELINE WORKER STARTED (Polling modular-orchestrator-queue)")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
