import asyncio
import os
import sys
from temporalio.client import Client
from src.workers.mayor_workflow import MayorWorkflow

async def run_validation(bead_id):
    os.environ["ENABLE_VIKUNJA"] = "false"
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)
    workflow_id = f"local-task-{bead_id}-validation"
    print(f"Starting MayorWorkflow for {bead_id} Validation...")
    handle = await client.start_workflow(
        MayorWorkflow.run,
        args=[bead_id, "Validation"],
        id=workflow_id,
        task_queue="main-orchestrator-queue",
    )
    result = await handle.result()
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(run_validation(sys.argv[1]))
