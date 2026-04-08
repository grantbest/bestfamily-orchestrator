import os
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger(__name__)

VERSION = "2.0.0-HEADLESS"

# --- Configuration & Feature Flags ---
ENABLE_VIKUNJA = os.getenv("ENABLE_VIKUNJA", "false").lower() == "true"
BEADS_DIR = Path("/Users/grantbest/Documents/Active/BestFam-Orchestrator/.beads")
BEADS_DIR.mkdir(parents=True, exist_ok=True)

# Configuration from Environment (Legacy Vikunja)
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "1")

def get_headers():
    if not VIKUNJA_API_TOKEN:
        return {}
    return {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }

# --- CORE BEAD OPERATIONS (MODULAR) ---

def create_bead(title: str, description: str, requesting_agent: str = "System", assigned_agent: str = None, stage: str = "PENDING", parent_id: str = None) -> str:
    """Creates a new bead (Vikunja or Local JSON)."""
    
    metadata = {
        "title": title,
        "description": description,
        "requesting_agent": requesting_agent,
        "assigned_agent": assigned_agent,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage.upper(),
        "workflow_id": None,
        "context": {},
        "resolution": None,
        "done": False,
        "parent_id": parent_id
    }

    if not ENABLE_VIKUNJA:
        # HEADLESS MODE: Write to JSON
        existing = list(BEADS_DIR.glob("*.json"))
        if not existing:
            new_id = "1"
        else:
            new_id = str(max(int(f.stem) for f in existing) + 1)
        metadata["id"] = new_id
        metadata["index"] = new_id
        
        with open(BEADS_DIR / f"{new_id}.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"📄 [HEADLESS] Created Bead #{new_id}: {title}")
        return new_id

    # VIKUNJA MODE
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks"
    payload = {
        "title": title,
        "description": f"{description}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}",
    }
    
    with httpx.Client() as client:
        resp = client.put(url, headers=get_headers(), json=payload)
        resp.raise_for_status()
        return str(resp.json()['id'])

def read_bead(bead_id: str) -> Dict[str, Any]:
    """Reads a bead from JSON or Vikunja."""
    if not ENABLE_VIKUNJA:
        path = BEADS_DIR / f"{bead_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Bead {bead_id} not found in {BEADS_DIR}")
        with open(path, "r") as f:
            return json.load(f)

    # VIKUNJA MODE
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}"
    with httpx.Client() as client:
        resp = client.get(url, headers=get_headers())
        if resp.status_code == 404:
            # Try searching by index
            idx_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks?filter=index%20%3D%20{bead_id}"
            resp = client.get(idx_url, headers=get_headers())
            task = resp.json()[0]
        else:
            task = resp.json()
        return _map_task_to_bead(task)

def update_bead(bead_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates a bead's metadata."""
    if not ENABLE_VIKUNJA:
        current = read_bead(bead_id)
        current.update(updates)
        # Update timestamp
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        with open(BEADS_DIR / f"{bead_id}.json", "w") as f:
            json.dump(current, f, indent=2)
        return current

    # VIKUNJA MODE
    current = read_bead(bead_id)
    stage = updates.get("stage", current.get("stage", "PENDING")).upper()
    
    metadata = {
        "stage": stage,
        "workflow_id": updates.get("workflow_id", current.get("workflow_id")),
        "resolution": updates.get("resolution", current.get("resolution")),
        "context": {**current.get("context", {}), **updates.get("context", {})}
    }
    
    payload = {
        "title": updates.get("title", current.get("title")),
        "description": f"{updates.get('description', current.get('description'))}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}"
    }

    # Map stage to Bucket ID
    # 1=To-Do, 4=Design, 2=Doing, 5=Validation, 3=Done
    bucket_map = {"PENDING": 1, "DESIGN": 4, "DOING": 2, "VALIDATION": 5, "DONE": 3}
    
    # SRE Debug
    logger.info(f"DEBUG: update_bead Task {bead_id} Stage: {stage} -> Bucket: {bucket_map.get(stage)}")
    
    with httpx.Client() as client:
        # 1. Update task title/desc
        resp = client.post(f"{VIKUNJA_BASE_URL}/tasks/{bead_id}", headers=get_headers(), json=payload)
        resp.raise_for_status()
        
        # 2. Move to bucket if stage mapped
        if stage in bucket_map:
            bid = bucket_map[stage]
            # SRE: In Vikunja, bucket moves are often managed via the view-bucket-task relationship
            # We assume project 1 and view 4 (Kanban) based on our setup
            move_url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/views/4/buckets/{bid}/tasks"
            try:
                m_resp = client.post(move_url, headers=get_headers(), json={"task_id": int(bead_id)})
                if m_resp.status_code != 200:
                    logger.error(f"SRE ERROR: Failed to move task {bead_id} to bucket {bid}. Status: {m_resp.status_code}, Body: {m_resp.text}")
                else:
                    logger.info(f"SRE SUCCESS: Moved task {bead_id} to bucket {bid}")
            except Exception as e:
                logger.error(f"SRE EXCEPTION moving task {bead_id}: {e}")
            
        return read_bead(bead_id)

def add_comment(bead_id: str, comment_text: str):
    if not ENABLE_VIKUNJA:
        print(f"💬 [HEADLESS] Comment on #{bead_id}: {comment_text}")
        return
    
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}/comments"
    payload = {"comment": f"{comment_text}\n\n[AGENT_SIGNATURE]"}
    with httpx.Client() as client:
        client.put(url, headers=get_headers(), json=payload)

def list_beads(status: str = None) -> List[Dict[str, Any]]:
    if not ENABLE_VIKUNJA:
        beads = []
        for path in BEADS_DIR.glob("*.json"):
            with open(path, "r") as f:
                beads.append(json.load(f))
        if status:
            beads = [b for b in beads if b["stage"] == status.upper()]
        return beads

    # VIKUNJA MODE
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks?per_page=100"
    with httpx.Client() as client:
        resp = client.get(url, headers=get_headers())
        tasks = resp.json()
        return [_map_task_to_bead(t) for t in tasks]

def _map_task_to_bead(task: Dict[str, Any]) -> Dict[str, Any]:
    desc = task.get("description", "")
    parts = desc.split("--- AGENT METADATA ---")
    metadata = {}
    if len(parts) > 1:
        try: metadata = json.loads(parts[1].strip())
        except: pass
    
    return {
        "id": str(task['id']), 
        "index": str(task['index']), 
        "title": task['title'],
        "stage": metadata.get("stage", "PENDING").upper(),
        "context": metadata.get("context", {}),
        "resolution": metadata.get("resolution"),
        "done": task.get("done", False)
    }

if __name__ == "__main__":
    import sys
    mode = "VIKUNJA" if ENABLE_VIKUNJA else "HEADLESS"
    print(f"🐝 BeadsManager v{VERSION} | Mode: {mode}")
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for b in list_beads():
            print(f"[{b['stage']}] #{b.get('id', '??')} : {b['title']}")
