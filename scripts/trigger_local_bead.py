import asyncio
import sys
import os
from temporalio.client import Client
from beads_manager import create_bead, read_bead

async def trigger_local_bead(title, description, bucket="Ready"):
    """
    Creates a local JSON bead and triggers the MayorWorkflow.
    """
    # Ensure headless mode is on
    os.environ["ENABLE_VIKUNJA"] = "false"
    
    # 1. Create the local bead
    bead_id = create_bead(
        title=title,
        description=description,
        requesting_agent="User-CLI",
        stage=bucket
    )
    
    # 2. Connect to Temporal
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    print(f"Connecting to Temporal at {temporal_address}...")
    client = await Client.connect(temporal_address)
    
    # 3. Start MayorWorkflow
    from src.workers.mayor_workflow import MayorWorkflow
    
    workflow_id = f"local-task-{bead_id}-{bucket.lower()}"
    print(f"🚀 Starting Headless MayorWorkflow for bead {bead_id}...")
    
    handle = await client.start_workflow(
        MayorWorkflow.run,
        args=[bead_id, bucket],
        id=workflow_id,
        task_queue="main-orchestrator-queue",
    )
    
    print(f"✅ Workflow started. ID: {workflow_id}, Run ID: {handle.result_run_id}")
    
    # Wait for result
    result = await handle.result()
    print(f"🏁 Workflow Result: {result}")
    
    # Show final bead status
    final_bead = read_bead(bead_id)
    print(f"📄 Final Bead Resolution: {final_bead.get('resolution', 'No resolution provided')}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 trigger_local_bead.py <title> <description> [bucket]")
        sys.exit(1)
    
    title = sys.argv[1]
    description = sys.argv[2]
    bucket = sys.argv[3] if len(sys.argv) > 3 else "Ready"
    
    asyncio.run(trigger_local_bead(title, description, bucket))
