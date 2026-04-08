import asyncio
import os
import sys
from temporalio.client import Client
from src.workers.pipeline_workflow import MasterPipelineWorkflow
# Add scripts to path for beads_manager
sys.path.append(os.path.join(os.path.dirname(__file__)))
from beads_manager import create_bead

async def trigger_pipeline(title, description):
    """
    Creates a bead and triggers the MasterPipelineWorkflow.
    """
    os.environ["ENABLE_VIKUNJA"] = "false"
    
    # 1. Create the bead
    bead_id = create_bead(
        title=title,
        description=description,
        requesting_agent="Gemini-CLI",
        stage="READY"
    )
    
    # 2. Trigger Temporal
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        print(f"🚀 Starting MasterPipelineWorkflow for bead {bead_id}...")
        
        # We start the workflow on the modular-orchestrator-queue as per unified_orchestrator
        handle = await client.start_workflow(
            MasterPipelineWorkflow.run,
            args=[bead_id, title, description],
            id=f"pipeline-task-{bead_id}",
            task_queue="modular-orchestrator-queue",
        )
        print(f"✅ Workflow started. ID: {handle.id}")
        return bead_id
    except Exception as e:
        print(f"❌ Failed to trigger Temporal Pipeline: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 trigger_pipeline.py <title> <description>")
        sys.exit(1)
    
    title = sys.argv[1]
    description = sys.argv[2]
    asyncio.run(trigger_pipeline(title, description))
