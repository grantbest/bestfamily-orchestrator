import os
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

VERSION = "1.5.2-SRE-FIXED"

# --- Bug 8: Robust .env loading ---
def _load_env():
    # Priority: Current dir -> Homelab/shared-services -> Root
    env_paths = [
        ".env",
        "../Homelab/shared-services/.env",
        "../../Homelab/shared-services/.env",
        "/app/Homelab/shared-services/.env"
    ]
    for path in env_paths:
        if os.path.exists(path):
            load_dotenv(path)
            return path
    return None

env_loaded_from = _load_env()

# Configuration from Environment
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "2")
VIKUNJA_KANBAN_VIEW_ID = os.getenv("VIKUNJA_KANBAN_VIEW_ID", "8")

# Confirmed Bucket IDs for Project 2 / View 8
BUCKET_IDS = {
    "PENDING": 4, "TO-DO": 4, "BACKLOG": 4,
    "DESIGN": 7, "TRIAGED": 7,
    "DOING": 5, "RUNNING": 5, "BREAKDOWN": 5, "IMPLEMENT": 5,
    "VALIDATION": 8, "VALIDATE": 8,
    "DONE": 6, "COMPLETED": 6
}

def get_headers():
    if not VIKUNJA_API_TOKEN:
        raise ValueError("VIKUNJA_API_TOKEN is not set. Environment not loaded correctly?")
    return {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }

def create_bead(title: str, description: str, requesting_agent: str, assigned_agent: str = None, stage: str = "PENDING", parent_id: str = None) -> str:
    """Creates a new bead directly in a Kanban bucket and optionally links to a parent."""
    # Bug 4: Ensure tasks are created with project association first
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks"
    
    metadata = {
        "requesting_agent": requesting_agent,
        "assigned_agent": assigned_agent,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage.upper(),
        "workflow_id": None,
        "context": {},
        "resolution": None
    }
    
    payload = {
        "title": title,
        "description": f"{description}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}",
    }
    
    with httpx.Client() as client:
        # Vikunja uses PUT for creating tasks in a project
        resp = client.put(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        task_id = str(resp.json()['id'])
        
        # Bug 4: Associate with the specific Kanban bucket in View 8
        try:
            move_to_bucket(task_id, stage.upper())
        except Exception as e:
            logging.error(f"Failed to move bead {task_id} to bucket {stage}: {e}")
        
        # Link to parent
        if parent_id:
            try:
                link_beads(parent_id, task_id, relation_kind="subtask")
            except Exception as e:
                logging.error(f"Failed to link bead {task_id} to parent {parent_id}: {e}")
            
        return task_id

def move_to_bucket(bead_id: str, stage_name: str):
    """Moves a task to a specific Kanban bucket in View 8."""
    bucket_id = BUCKET_IDS.get(stage_name.upper())
    if not bucket_id:
        logging.warning(f"Unknown stage '{stage_name}', cannot move to bucket.")
        return

    # If DONE, mark task as done
    if stage_name.upper() in ["DONE", "COMPLETED"]:
        with httpx.Client() as client:
            client.post(f"{VIKUNJA_BASE_URL}/tasks/{bead_id}", headers=get_headers(), json={"done": True})

    # Bug 4: Associate with View 8 explicitly
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/views/{VIKUNJA_KANBAN_VIEW_ID}/buckets/{bucket_id}/tasks"
    payload = {"task_id": int(bead_id)}
    
    with httpx.Client() as client:
        resp = client.post(url, headers=get_headers(), json=payload)
        # 400 might mean it's already in the bucket, which is fine
        if resp.status_code not in [200, 201, 400]:
            resp.raise_for_status()

def link_beads(parent_id: str, child_id: str, relation_kind: str = "subtask"):
    """Links two beads using task relations."""
    url = f"{VIKUNJA_BASE_URL}/tasks/{child_id}/relations"
    payload = {
        "other_task_id": int(parent_id),
        "relation_kind": relation_kind
    }
    with httpx.Client() as client:
        resp = client.put(url, headers=get_headers(), json=payload)
        if resp.status_code not in [200, 201, 400]:
            resp.raise_for_status()

def update_bead(bead_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates properties and ensures bucket association (Bug 5: Atomicity)."""
    current = read_bead(bead_id)
    new_stage = updates.get("stage", current.get("stage", "PENDING")).upper()
    
    new_context = current.get("context", {})
    if "context" in updates: new_context.update(updates["context"])
    
    metadata = {
        "requesting_agent": updates.get("requesting_agent", current.get("requesting_agent")),
        "assigned_agent": updates.get("assigned_agent", current.get("assigned_agent")),
        "created_at": current.get("created_at"),
        "stage": new_stage,
        "workflow_id": updates.get("workflow_id", current.get("workflow_id")),
        "resolution": updates.get("resolution", current.get("resolution")),
        "context": new_context
    }
    
    payload = {
        "title": updates.get("title", current.get("title")),
        "description": f"{updates.get('description', current.get('description'))}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}"
    }
    
    if "done" in updates: payload["done"] = updates["done"]
    elif new_stage in ["DONE", "COMPLETED"]: payload["done"] = True

    with httpx.Client() as client:
        # 1. Update task properties (Metadata)
        resp = client.post(f"{VIKUNJA_BASE_URL}/tasks/{current['id']}", headers=get_headers(), json=payload)
        resp.raise_for_status()
        
        # 2. Update bucket (UI Sync)
        if "stage" in updates or new_stage != current.get("stage"):
            try:
                move_to_bucket(current['id'], new_stage)
            except Exception as e:
                logging.error(f"Sync error: Updated metadata for {bead_id} but failed to move bucket to {new_stage}: {e}")
            
        return read_bead(current['id'])

def read_bead(bead_id: str) -> Dict[str, Any]:
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}"
    with httpx.Client() as client:
        resp = client.get(url, headers=get_headers())
        if resp.status_code == 404:
            idx_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks?filter=index%20%3D%20{bead_id}"
            resp = client.get(idx_url, headers=get_headers())
            task = resp.json()[0]
        else:
            task = resp.json()
        return _map_task_to_bead(task)

def list_beads(status: str = None) -> List[Dict[str, Any]]:
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks?per_page=100&sort_by[]=id&order_by[]=desc"
    with httpx.Client() as client:
        resp = client.get(url, headers=get_headers())
        tasks = resp.json()
        beads = [_map_task_to_bead(t) for t in tasks]
        if status: beads = [b for b in beads if b["stage"] == status.upper()]
        return beads

def delete_bead(bead_id: str):
    """Deletes a task from Vikunja."""
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}"
    with httpx.Client() as client:
        resp = client.delete(url, headers=get_headers())
        if resp.status_code in [200, 204]:
            print(f"✅ Deleted bead {bead_id}")
        else:
            print(f"❌ Failed to delete bead {bead_id}: {resp.text}")

def add_comment(bead_id: str, comment_text: str):
    """Adds a comment with AGENT signature."""
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}/comments"
    payload = {"comment": f"{comment_text}\n\n[AGENT_SIGNATURE]"}
    with httpx.Client() as client:
        client.put(url, headers=get_headers(), json=payload)

def upload_attachment(bead_id: str, file_path: str):
    """Uploads a file attachment."""
    if not os.path.exists(file_path): return
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}/attachments"
    with open(file_path, "rb") as f:
        files = {"files": (os.path.basename(file_path), f)}
        with httpx.Client() as client:
            client.put(url, headers=get_headers(), files=files)

def _map_task_to_bead(task: Dict[str, Any]) -> Dict[str, Any]:
    desc = task.get("description", "")
    parts = desc.split("--- AGENT METADATA ---")
    metadata = {}
    if len(parts) > 1:
        try: metadata = json.loads(parts[1].strip())
        except: pass
    
    return {
        "id": str(task['id']), "index": str(task['index']), "title": task['title'],
        "stage": metadata.get("stage", "PENDING").upper(),
        "requesting_agent": metadata.get("requesting_agent"),
        "assigned_agent": metadata.get("assigned_agent"),
        "created_at": metadata.get("created_at"),
        "workflow_id": metadata.get("workflow_id"),
        "context": metadata.get("context", {}),
        "resolution": metadata.get("resolution"),
        "bucket_id": task.get("bucket_id"),
        "done": task.get("done")
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for b in list_beads():
            print(f"[{b['stage']}] #{b['index']} (Done: {b['done']}): {b['title']}")
