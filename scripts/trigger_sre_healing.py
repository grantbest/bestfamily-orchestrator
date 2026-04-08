import asyncio
import sys
import os
import json
from temporalio.client import Client
# Add scripts dir to path for beads_manager
sys.path.append(os.path.dirname(__file__))
from beads_manager import create_bead

async def trigger_sre_healing(title, issue_details):
    """
    Directly triggers an SRE healing workflow via Mayor.
    """
    os.environ["ENABLE_VIKUNJA"] = "false"
    
    # 1. Create a high-priority "Healing" bead
    bead_id = create_bead(
        title=f"[SRE HEALING] {title}",
        description=f"CRITICAL SYSTEM FAILURE DETECTED.\n\nIssue: {title}\nDetails: {issue_details}\n\nACTION: Engage SRE sub-agent to diagnose and recover service connectivity or alerting logic.",
        requesting_agent="MLB-Betting-Engine",
        stage="DOING"
    )
    
    # 2. Trigger the Mayor to process it
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    try:
        client = await Client.connect(temporal_address)
        
        # We trigger the MayorWorkflow directly in DOING bucket
        # In src.workers.mayor_workflow, DOING -> routes to SRE if it's a healing task
        from src.workers.mayor_workflow import MayorWorkflow
        
        workflow_id = f"sre-healing-task-{bead_id}"
        print(f"🚀 Dispatching SRE via Mayor for bead {bead_id}...")
        
        await client.execute_workflow(
            MayorWorkflow.run,
            args=[bead_id, "Doing"],
            id=workflow_id,
            task_queue="main-orchestrator-queue",
        )
        print(f"✅ SRE Healing Workflow completed for bead {bead_id}.")
    except Exception as e:
        print(f"❌ Failed to trigger Temporal SRE Workflow: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 trigger_sre_healing.py <title> <details>")
        sys.exit(1)
    
    title = sys.argv[1]
    details = sys.argv[2]
    asyncio.run(trigger_sre_healing(title, details))
