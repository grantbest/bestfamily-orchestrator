import asyncio
import sys
import os
from temporalio.client import Client

# Ensure we can import from the current directory
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "scripts"))

async def trigger_mayor_implementation(bead_id, bucket="Ready"):
    """
    Triggers the MayorWorkflow specifically for implementation.
    'Ready' bucket in MayorWorkflow triggers the Polecat developer_activity.
    """
    # Connect to Temporal
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)

    print(f"🏛️ Mayor: Triggering implementation for Bead {bead_id}...")
    
    # Start the MayorWorkflow
    handle = await client.start_workflow(
        "MayorWorkflow",
        args=[bead_id, bucket],
        id=f"mayor-{bucket.lower()}-{bead_id}-{int(asyncio.get_event_loop().time())}",
        task_queue="main-orchestrator-queue"
    )

    print(f"🚀 Gastown Engine: Workflow started successfully.")
    print(f"ID: {handle.id}")
    print(f"Run ID: {handle.first_execution_run_id}")
    print(f"🛰️  Broadcast: Monitor progress at https://tracker-dev.bestfam.us/tasks/{bead_id}")
    
    # We exit immediately instead of awaiting handle.result()
    return

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mayor_trigger.py <bead_id> [bucket]")
        sys.exit(1)
    
    bead_id = sys.argv[1]
    bucket = sys.argv[2] if len(sys.argv) > 2 else "Ready"
    
    asyncio.run(trigger_mayor_implementation(bead_id, bucket))
