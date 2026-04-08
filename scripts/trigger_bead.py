import asyncio
import sys
from temporalio.client import Client
from beads_manager import create_bead, read_bead

async def trigger_bead(bead_id, workflow_name="DesignWorkflow"):
    # 2. Connect to Temporal
    client = await Client.connect("localhost:7233")

    print(f"Starting {workflow_name} for bead {bead_id}...")
    handle = await client.start_workflow(
        workflow_name,
        args=[str(bead_id)],
        id=f"agile-task-{bead_id}-{int(asyncio.get_event_loop().time())}",
        task_queue="modular-orchestrator-queue"
    )

    print(f"Workflow started. ID: {handle.id}, Run ID: {handle.first_execution_run_id}")
    return handle

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trigger_bead.py <bead_id> [workflow_name]")
        sys.exit(1)
    
    bead_id = sys.argv[1]
    workflow_name = sys.argv[2] if len(sys.argv) > 2 else "DesignWorkflow"
    
    asyncio.run(trigger_bead(bead_id, workflow_name))
