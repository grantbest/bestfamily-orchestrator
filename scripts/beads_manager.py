import os
import json
import httpx
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path

# Ensure project root is in path for relative imports if run as script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.utils.identity_manager import IdentityManager
except ImportError:
    # Fallback for direct script execution without proper PYTHONPATH
    sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "BestFam-Orchestrator")))
    from src.utils.identity_manager import IdentityManager

# Setup logging
logger = logging.getLogger(__name__)

VERSION = "3.1.0-SIDECAR-RESILIENT"

# --- Configuration ---
ENABLE_VIKUNJA = os.getenv("ENABLE_VIKUNJA", "false").lower() == "true"
BEADS_DIR = Path("/Users/grantbest/Documents/Active/BestFam-Orchestrator/.beads")
BEADS_DIR.mkdir(parents=True, exist_ok=True)

SIDECAR_URL = "http://localhost:8001"
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "1")

def get_headers():
    token = IdentityManager.get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def _api_call(method: str, path: str, **kwargs):
    """SRE: Forward requests to the Resiliency Sidecar."""
    url = f"{SIDECAR_URL}/{path}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

# --- CORE BEAD OPERATIONS ---

def create_bead(title: str, description: str, requesting_agent: str = "System", assigned_agent: str = None, stage: str = "PENDING", parent_id: str = None) -> str:
    metadata = {
        "title": title, "description": description, "requesting_agent": requesting_agent,
        "assigned_agent": assigned_agent, "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage.upper(), "workflow_id": None, "context": {}, "resolution": None,
        "done": False, "parent_id": parent_id
    }
    if not ENABLE_VIKUNJA:
        existing = list(BEADS_DIR.glob("*.json"))
        new_id = str(max([int(f.stem) for f in existing] + [0]) + 1)
        with open(BEADS_DIR / f"{new_id}.json", "w") as f: json.dump(metadata, f, indent=2)
        return new_id

    # VIKUNJA MODE
    payload = {
        "title": title,
        "description": f"{description}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}",
    }
    resp = _api_call("PUT", f"projects/{VIKUNJA_PROJECT_ID}/tasks", json=payload)
    return str(resp.json()['id'])

def read_bead(bead_id: str) -> Dict[str, Any]:
    """Reads a bead from JSON or Vikunja."""
    if not ENABLE_VIKUNJA:
        path = BEADS_DIR / f"{bead_id}.json"
        if not path.exists(): return None
        with open(path, "r") as f: return json.load(f)

    # SRE: Strictly use direct ID lookup. Fallback to index is too fragile.
    try:
        resp = _api_call("GET", f"tasks/{bead_id}")
        return _map_task_to_bead(resp.json())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise


def update_bead(bead_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not ENABLE_VIKUNJA:
        current = read_bead(bead_id)
        if not current: return None
        current.update(updates)
        with open(BEADS_DIR / f"{bead_id}.json", "w") as f: json.dump(current, f, indent=2)
        return current

    current = read_bead(bead_id)
    if not current: raise ValueError(f"Task {bead_id} not found.")

    stage = updates.get("stage", current.get("stage", "PENDING")).upper()
    metadata = {
        "stage": stage,
        "workflow_id": updates.get("workflow_id", current.get("workflow_id")),
        "resolution": updates.get("resolution", current.get("resolution")),
        "context": {**current.get("context", {}), **updates.get("context", {})}
    }
    new_desc_body = updates.get("description", current.get("description", ""))
    payload = {
        "title": updates.get("title", current.get("title")),
        "description": f"{new_desc_body}\n\n--- AGENT METADATA ---\n{json.dumps(metadata, indent=2)}"
    }
    bucket_map = {"PENDING": 1, "DESIGN": 4, "DOING": 2, "VALIDATION": 5, "DONE": 3}
    
    _api_call("POST", f"tasks/{bead_id}", json=payload)
    if stage in bucket_map:
        _api_call("POST", f"projects/{VIKUNJA_PROJECT_ID}/views/4/buckets/{bucket_map[stage]}/tasks", json={"task_id": int(bead_id)})
    return read_bead(bead_id)

def upload_attachment(bead_id: str, file_path: str):
    if not ENABLE_VIKUNJA: return
    with open(file_path, "rb") as f:
        _api_call("PUT", f"tasks/{bead_id}/attachments", files={"files": (os.path.basename(file_path), f)})

def add_comment(bead_id: str, comment_text: str):
    if not ENABLE_VIKUNJA: return
    _api_call("PUT", f"tasks/{bead_id}/comments", json={"comment": f"{comment_text}\n\n[AGENT_SIGNATURE]"})

def list_beads(status: str = None) -> List[Dict[str, Any]]:
    if not ENABLE_VIKUNJA:
        beads = []
        for path in BEADS_DIR.glob("*.json"):
            with open(path, "r") as f: beads.append(json.load(f))
        if status: beads = [b for b in beads if b["stage"] == status.upper()]
        return beads
    resp = _api_call("GET", f"projects/{VIKUNJA_PROJECT_ID}/tasks?per_page=100")
    return [_map_task_to_bead(t) for t in resp.json()]

def _map_task_to_bead(task: Dict[str, Any]) -> Dict[str, Any]:
    if not task or not isinstance(task, dict): return {}
    desc = task.get("description", "")
    parts = desc.split("--- AGENT METADATA ---")
    raw_desc = parts[0].strip() if len(parts) > 0 else ""
    metadata = {}
    if len(parts) > 1:
        try: metadata = json.loads(parts[1].strip())
        except: pass
    return {
        "id": str(task.get('id', '')), "index": str(task.get('index', '')), 
        "title": task.get('title', 'No Title'), "description": raw_desc,
        "stage": metadata.get("stage", "PENDING").upper(), "context": metadata.get("context", {}),
        "resolution": metadata.get("resolution"), "done": task.get("done", False)
    }

if __name__ == "__main__":
    mode = "VIKUNJA" if ENABLE_VIKUNJA else "HEADLESS"
    print(f"🐝 BeadsManager v{VERSION} | Mode: {mode}")
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for b in list_beads():
            print(f"[{b['stage']}] #{b.get('id', '??')} : {b['title']}")
