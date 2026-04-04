import asyncio
import sys
from temporalio.client import Client
from beads_manager import create_bead, read_bead

async def trigger_bead(title, description):
    # 1. Create the bead
    bead_id = create_bead(
        title=title,
        description=description,
        requesting_agent="user-manual-trigger"
    )
    print(f"Bead created: {bead_id}")

    # 2. Connect to Temporal
    client = await Client.connect("localhost:7233")

    # 3. Start the MayorWorkflow on the main-orchestrator-queue
    # Note: We use string reference for the workflow name to match the definition
    print(f"Starting MayorWorkflow for bead {bead_id}...")
    handle = await client.start_workflow(
        "MayorWorkflow",
        args=[bead_id, "Design"],
        id=f"agile-task-{bead_id}-design-manual",
        task_queue="main-orchestrator-queue"
    )

    print(f"Workflow started. ID: {handle.id}, Run ID: {handle.first_execution_run_id}")
    
    # Wait for result (optional, but good for CLI feedback)
    result = await handle.result()
    print(f"\nWorkflow finished successfully!")
    print(f"Result: {result}")
    
    # Show final bead status
    final_bead = read_bead(bead_id)
    print(f"Final Bead Status: {final_bead['status']}")
    print(f"Resolution: {final_bead['resolution']}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 trigger_bead.py <title> <description>")
        print("Example: python3 trigger_bead.py 'Fix CSS' 'The button on the homepage is misaligned.'")
        sys.exit(1)
    
    title = sys.argv[1]
    description = sys.argv[2]
    
    asyncio.run(trigger_bead(title, description))
