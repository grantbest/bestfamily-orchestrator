import os
import json
import httpx
from typing import Dict, Any

# Hardcoded for diagnostic - matching your environment
VIKUNJA_BASE_URL = "https://tracker.bestfam.us/api/v1"
VIKUNJA_API_TOKEN = "tk_12e196e19221fcf2a6c649a2e2ff41f4461d3f3e"
VIKUNJA_PROJECT_ID = "2"

def get_headers():
    return {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }

def diagnose():
    print(f"🔍 Diagnosing Vikunja Project {VIKUNJA_PROJECT_ID}...")
    
    # 1. List Views to find the Kanban View ID
    views_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/views"
    with httpx.Client() as client:
        resp = client.get(views_url, headers=get_headers())
        print(f"\n--- Views in Project {VIKUNJA_PROJECT_ID} ---")
        views = resp.json()
        kanban_view_id = None
        for v in views:
            print(f"ID: {v['id']} | Title: {v['title']} | Kind: {v['view_kind']}")
            if v['view_kind'] == 'kanban':
                kanban_view_id = v['id']
        
        if not kanban_view_id:
            print("❌ No Kanban view found!")
            return

        # 2. List Buckets for that Kanban View
        buckets_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/views/{kanban_view_id}/buckets"
        resp = client.get(buckets_url, headers=get_headers())
        print(f"\n--- Buckets in View {kanban_view_id} ---")
        buckets = resp.json()
        bucket_map = {}
        for b in buckets:
            print(f"ID: {b['id']} | Title: {b['title']}")
            bucket_map[b['title']] = b['id']

        # 3. Create a test task
        print("\n--- Testing Task Creation ---")
        create_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks"
        task_payload = {
            "title": "DIAGNOSTIC TEST TASK",
            "description": "If you see this, create_task works."
        }
        resp = client.put(create_url, headers=get_headers(), json=task_payload)
        if resp.status_code == 201:
            task = resp.json()
            task_id = task['id']
            print(f"✅ Task Created! ID: {task_id}")
            
            # 4. Test Move to 'Doing' (if it exists)
            if "Doing" in bucket_map:
                doing_id = bucket_map["Doing"]
                print(f"\n--- Testing Move to 'Doing' (ID: {doing_id}) ---")
                # According to docs, update task to move bucket
                move_url = f"{VIKUNJA_BASE_URL}/tasks/{task_id}"
                # TRY POST first
                move_resp = client.post(move_url, headers=get_headers(), json={"bucket_id": doing_id})
                if move_resp.status_code == 200:
                    print(f"✅ Task Moved successfully via POST!")
                else:
                    print(f"❌ Move failed (POST). Status: {move_resp.status_code} | {move_resp.text}")
                    # TRY PUT?
                    move_resp = client.put(move_url, headers=get_headers(), json={"bucket_id": doing_id})
                    if move_resp.status_code == 200:
                        print(f"✅ Task Moved successfully via PUT!")
                    else:
                        print(f"❌ Move failed (PUT). Status: {move_resp.status_code} | {move_resp.text}")
        else:
            print(f"❌ Task Creation failed. Status: {resp.status_code} | {resp.text}")

if __name__ == "__main__":
    diagnose()
