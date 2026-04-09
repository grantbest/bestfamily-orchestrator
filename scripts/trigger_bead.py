import asyncio
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from temporalio.client import Client
from scripts.beads_manager import read_bead, ENABLE_VIKUNJA
from src.utils.namespace_manager import NamespaceManager

async def trigger_bead(bead_id, workflow_name="DesignWorkflow"):
    print(f"DEBUG: ENABLE_VIKUNJA={ENABLE_VIKUNJA}")
    # 1. Fetch bead to determine namespace
    bead = read_bead(bead_id)
    if not bead:
        print(f"Error: Bead {bead_id} not found.")
        return

    target_ns = NamespaceManager.get_namespace_for_task(title=bead['title'])
    print(f"DEBUG: Title='{bead['title']}' resolved to Namespace='{target_ns}'")
    target_queue = NamespaceManager.get_queue_for_namespace(target_ns)

    # 2. Connect to Temporal
    client = await Client.connect("localhost:7233", namespace=target_ns)

    print(f"Starting {workflow_name} for bead {bead_id} in namespace {target_ns}...")
    handle = await client.start_workflow(
        workflow_name,
        args=[str(bead_id)],
        id=f"agile-task-{bead_id}-{int(asyncio.get_event_loop().time())}",
        task_queue=target_queue
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
