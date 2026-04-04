import asyncio
import os
import sys
import uuid
from temporalio.client import Client

# Add scripts to path for beads_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from beads_manager import create_bead

async def main():
    # 1. Create a task that will trigger RefineryWorkflow
    # Strategy logic: [STORY] in title -> IMPLEMENTATION
    title = f"[STORY] NEXUS PROTOTYPE TEST {uuid.uuid4().hex[:4]}"
    description = "Testing cross-boundary security audit via Temporal Nexus endpoint."
    
    print(f"📝 Creating task: {title}")
    bead_id = create_bead(
        title=title,
        description=description,
        requesting_agent="architect-test",
        stage="VALIDATION" # This might trigger webhook, or we start workflow manually
    )
    print(f"✅ Created Bead ID: {bead_id}")

    # 2. Manually start the RefineryWorkflow for this bead
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_address)
    
    workflow_id = f"nexus-test-workflow-{bead_id}"
    print(f"🚀 Starting RefineryWorkflow (ID: {workflow_id})")
    
    handle = await client.start_workflow(
        "RefineryWorkflow",
        bead_id,
        id=workflow_id,
        task_queue="modular-orchestrator-queue"
    )
    
    print(f"⏳ Workflow started. Waiting for result...")
    result = await handle.result()
    print(f"🏁 Workflow Result: {result}")
    print("\nCheck unified.log for 'Requesting cross-boundary Security Audit via Nexus...' to confirm success.")

if __name__ == "__main__":
    asyncio.run(main())
