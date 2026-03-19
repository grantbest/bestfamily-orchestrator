import os
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

VERSION = "1.5.1-RESTORED-FUNCTIONS"

# Configuration from Environment
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "2")
VIKUNJA_KANBAN_VIEW_ID = os.getenv("VIKUNJA_KANBAN_VIEW_ID", "8")

# Confirmed Bucket IDs for Project 2 / View 8
BUCKET_IDS = {
    "PENDING": 4, "TO-DO": 4,
    "DESIGN": 7, "TRIAGED": 7,
    "DOING": 5, "RUNNING": 5, "BREAKDOWN": 5, "IMPLEMENT": 5,
    "VALIDATION": 8, "VALIDATE": 8,
    "DONE": 6, "COMPLETED": 6
}

def get_headers():
    if not VIKUNJA_API_TOKEN:
        raise ValueError("VIKUNJA_API_TOKEN is not set.")
    return {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }

def create_bead(title: str, description: str, requesting_agent: str, assigned_agent: str = None, stage: str = "PENDING", parent_id: str = None) -> str:
    """Creates a new bead directly in a Kanban bucket and optionally links to a parent."""
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
        resp = client.put(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        task_id = str(resp.json()['id'])
        
        # Associate with the specific Kanban bucket
        move_to_bucket(task_id, stage.upper())
        
        # Link to parent
        if parent_id:
            link_beads(parent_id, task_id, relation_kind="subtask")
            
        return task_id

def move_to_bucket(bead_id: str, stage_name: str):
    """Moves a task to a specific Kanban bucket."""
    bucket_id = BUCKET_IDS.get(stage_name.upper())
    if not bucket_id: return

    if stage_name.upper() in ["DONE", "COMPLETED"]:
        with httpx.Client() as client:
            client.post(f"{VIKUNJA_BASE_URL}/tasks/{bead_id}", headers=get_headers(), json={"done": True})

    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/views/{VIKUNJA_KANBAN_VIEW_ID}/buckets/{bucket_id}/tasks"
    payload = {"task_id": int(bead_id)}
    
    with httpx.Client() as client:
        client.post(url, headers=get_headers(), json=payload)

def link_beads(parent_id: str, child_id: str, relation_kind: str = "subtask"):
    """Links two beads using task relations."""
    url = f"{VIKUNJA_BASE_URL}/tasks/{child_id}/relations"
    payload = {
        "other_task_id": int(parent_id),
        "relation_kind": relation_kind
    }
    with httpx.Client() as client:
        resp = client.put(url, headers=get_headers(), json=payload)

def update_bead(bead_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates properties and ensures bucket association."""
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
        client.post(f"{VIKUNJA_BASE_URL}/tasks/{current['id']}", headers=get_headers(), json=payload)
        if "stage" in updates:
            move_to_bucket(current['id'], new_stage)
            
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
