import os
import time
import asyncio
import json
import httpx
import sys
from datetime import datetime, timezone

# Add scripts to path for beads_manager import
sys.path.append(os.path.join(os.getcwd(), "BestFam-Orchestrator", "scripts"))
from beads_manager import create_bead, read_bead, update_bead, list_beads, move_to_bucket, get_headers
from temporalio.client import Client

# Configuration
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN", "tk_12e196e19221fcf2a6c649a2e2ff41f4461d3f3e")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "2")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

async def get_temporal_client():
    return await Client.connect(TEMPORAL_ADDRESS)

async def test_epic_breakdown_modular():
    print("\n🚀 Testing MODULAR Epic Breakdown...")
    
    # 1. Create a fresh Epic
    epic_title = f"[EPIC] Modular TDD {int(time.time())}"
    epic_desc = "Break this into 2 modular stories. Verify specialized BreakdownWorkflow triggers."
    epic_id = create_bead(epic_title, epic_desc, "regression-tester")
    print(f"✅ Created Epic: {epic_title} (ID: {epic_id})")
    
    # 2. Trigger BreakdownWorkflow
    print(f"🤖 Triggering BreakdownWorkflow for Epic {epic_id}...")
    client = await get_temporal_client()
    workflow_id = f"agile-task-{epic_id}-breakdown"
    
    try:
        await client.start_workflow(
            "BreakdownWorkflow",
            args=[str(epic_id)], # Use keyword args
            id=workflow_id,
            task_queue="modular-orchestrator-queue",
        )
    except Exception as e:
        print(f"⚠️ Workflow start error: {e}")

    # 3. Wait for child stories
    print("⏳ Waiting for stories to be created (max 60s)...")
    success = False
    for i in range(12):
        await asyncio.sleep(5)
        all_beads = list_beads()
        children = [b for b in all_beads if b.get('requesting_agent') == "quarterback-breakdown"]
        
        recent_children = []
        now = datetime.now(timezone.utc)
        for c in children:
            try:
                # Vikunja created_at: 2026-03-19T22:04:06.123456+00:00 or similar
                # Handle both with and without micro/timezone
                ts_str = c['created_at'].replace('Z', '+00:00')
                created = datetime.fromisoformat(ts_str)
                
                # If naive, make it aware (assuming UTC)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                
                diff = (now - created).total_seconds()
                if diff < 180: # 3 minutes
                    recent_children.append(c)
            except Exception as e:
                print(f"Error parsing date {c.get('created_at')}: {e}")

        if len(recent_children) >= 1:
            print(f"✅ SUCCESS: Modular breakdown created {len(recent_children)} stories.")
            success = True
            break
        print(f"... still waiting (found {len(recent_children)} matching stories)")

    if not success:
        print("❌ FAILED: Epic breakdown did not complete.")
        return False
    return True

async def test_story_implementation_modular():
    print("\n🚀 Testing MODULAR Story Implementation...")
    
    # 1. Create a Story
    story_title = f"[STORY] Modular Implementation {int(time.time())}"
    story_desc = "Verify implementation workflow triggers specialized ImplementationWorkflow."
    story_id = create_bead(story_title, story_desc, "regression-tester")
    print(f"✅ Created Story: {story_id}")
    
    # 2. Trigger ImplementationWorkflow
    print(f"🤖 Triggering ImplementationWorkflow for Story {story_id}...")
    client = await get_temporal_client()
    workflow_id = f"agile-task-{story_id}-implement"
    
    try:
        await client.start_workflow(
            "ImplementationWorkflow",
            args=[str(story_id)], # Use keyword args
            id=workflow_id,
            task_queue="modular-orchestrator-queue",
        )
    except Exception as e:
        print(f"⚠️ Workflow start error: {e}")

    # 3. Wait for progress
    print("⏳ Waiting for implementation progress (max 60s)...")
    for _ in range(12):
        await asyncio.sleep(5)
        bead = read_bead(story_id)
        # Check stage field
        stage = bead.get("stage", "").upper()
        if stage in ["VALIDATION", "VALIDATE"]:
            print(f"✅ SUCCESS: Implementation complete, moved to Validation.")
            return True
        print(f"... current stage: {stage}")

    print("❌ FAILED: Implementation workflow timed out.")
    return False

async def main():
    res1 = await test_epic_breakdown_modular()
    res2 = await test_story_implementation_modular()
    
    if res1 and res2:
        print("\n🏆 ALL MODULAR REGRESSION TESTS PASSED.")
    else:
        print("\n❌ MODULAR REGRESSION TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
