import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker, UnsandboxedWorkflowRunner

# Workflows
from src.workers.sre_workflow import SREHealingWorkflow

# Activities
from src.workers.sre_activities import (
    sre_site_monitor_activity,
    sre_check_temporal_health_activity,
    sre_log_audit_activity,
    sre_check_vikunja_bugs_activity,
    sre_remediate_issue_activity
)

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("SREWorker")
    
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        logger.info(f"🛡️ SRE Worker: Connected to Temporal at {temporal_address}")
    except Exception as e:
        logger.error(f"🛡️ SRE Worker: Failed to connect to Temporal: {e}")
        return

    # The SRE Worker handles monitoring and healing
    worker = Worker(
        client,
        task_queue="sre-queue",
        workflows=[SREHealingWorkflow],
        activities=[
            sre_site_monitor_activity, 
            sre_check_temporal_health_activity,
            sre_log_audit_activity,
            sre_check_vikunja_bugs_activity,
            sre_remediate_issue_activity
        ],
        workflow_runner=UnsandboxedWorkflowRunner(),
        max_concurrent_activities=10 # Allow parallel tasks
    )

    logger.info("🛡️ SRE WORKER STARTED (Polling sre-queue)")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
