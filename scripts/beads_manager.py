import os
import json
import uuid
import httpx
from datetime import datetime
from pathlib import Path

# Configuration from Environment
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
VIKUNJA_PROJECT_ID = os.getenv("VIKUNJA_PROJECT_ID", "2")

def get_headers():
    return {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }

def create_bead(title, description, requesting_agent, assigned_agent=None):
    """Creates a new bead as a Vikunja task."""
    if not VIKUNJA_API_TOKEN:
        print("Vikunja API Token not set. Falling back to local file (legacy).")
        return create_legacy_bead(title, description, requesting_agent, assigned_agent)

    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks"
    
    payload = {
        "title": title,
        "description": f"{description}\n\n--- AGENT METADATA ---\n" + json.dumps({
            "requesting_agent": requesting_agent,
            "assigned_agent": assigned_agent,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending"
        }, indent=2)
    }
    
    try:
        with httpx.Client() as client:
            # Vikunja project endpoint requires PUT for task creation
            response = client.put(url, headers=get_headers(), json=payload)
            response.raise_for_status()
            task = response.json()
            bead_id = str(task['id'])
            print(f"Created Vikunja bead: {bead_id}")
            return bead_id
    except Exception as e:
        print(f"Failed to create Vikunja task: {e}")
        return create_legacy_bead(title, description, requesting_agent, assigned_agent)

def read_bead(bead_id):
    """Reads a bead from Vikunja."""
    if not str(bead_id).isdigit():
        return read_legacy_bead(bead_id)

    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}"
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=get_headers())
            response.raise_for_status()
            task = response.json()
            
            desc_parts = task.get("description", "").split("--- AGENT METADATA ---")
            metadata = {}
            clean_desc = task.get("description", "")
            if len(desc_parts) > 1:
                try:
                    metadata = json.loads(desc_parts[1].strip())
                    clean_desc = desc_parts[0].strip()
                except:
                    pass
            
            return {
                "id": str(task['id']),
                "title": task['title'],
                "description": clean_desc,
                "status": metadata.get("status", "pending"),
                "requesting_agent": metadata.get("requesting_agent"),
                "assigned_agent": metadata.get("assigned_agent"),
                "created_at": metadata.get("created_at"),
                "updated_at": task.get("updated"),
                "context": metadata.get("context", {}),
                "resolution": metadata.get("resolution")
            }
    except Exception as e:
        print(f"Failed to read Vikunja task {bead_id}: {e}")
        raise FileNotFoundError(f"Bead {bead_id} not found in Vikunja.")

def update_bead(bead_id, updates):
    """Updates a bead in Vikunja."""
    if not str(bead_id).isdigit():
        return update_legacy_bead(bead_id, updates)

    current = read_bead(bead_id)
    
    status = updates.get("status", current.get("status"))
    resolution = updates.get("resolution", current.get("resolution"))
    context = current.get("context", {})
    if "context" in updates:
        context.update(updates["context"])
    
    new_metadata = {
        "requesting_agent": current.get("requesting_agent"),
        "assigned_agent": current.get("assigned_agent"),
        "created_at": current.get("created_at"),
        "status": status,
        "resolution": resolution,
        "context": context
    }
    
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}"
    payload = {
        "title": updates.get("title", current.get("title")),
        "description": f"{updates.get('description', current.get('description'))}\n\n--- AGENT METADATA ---\n" + json.dumps(new_metadata, indent=2)
    }
    
    # Explicitly handle the 'done' state
    if "done" in updates:
        payload["done"] = updates["done"]
    elif status == "completed":
        payload["done"] = True
    else:
        # Default to False for all other active states
        payload["done"] = False

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=get_headers(), json=payload)
            response.raise_for_status()
            print(f"Updated Vikunja bead: {bead_id}")
            return read_bead(bead_id)
    except Exception as e:
        print(f"Failed to update Vikunja task {bead_id}: {e}")
        return update_legacy_bead(bead_id, updates)

def list_beads(status=None):
    if not VIKUNJA_API_TOKEN:
        return []
    
    url = f"{VIKUNJA_BASE_URL}/projects/{VIKUNJA_PROJECT_ID}/tasks"
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=get_headers())
            response.raise_for_status()
            tasks = response.json()
            return [{"id": str(t['id']), "title": t['title'], "status": "vikunja"} for t in tasks]
    except:
        return []

# --- Legacy Support ---
def get_beads_dirs():
    paths = [Path("/app/Homelab/.beads"), Path("/app/BettingApp/.beads"), Path(".beads")]
    return [p for p in paths if p.exists() and p.is_dir()]

def create_legacy_bead(title, description, requesting_agent, assigned_agent=None):
    bead_id = str(uuid.uuid4())
    bead_data = {
        "id": bead_id, "title": title, "description": description, "status": "pending",
        "requesting_agent": requesting_agent, "assigned_agent": assigned_agent,
        "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat(),
        "context": {}, "resolution": None
    }
    dirs = get_beads_dirs()
    file_path = (dirs[0] if dirs else Path(".beads")) / f"{bead_id}.json"
    with open(file_path, "w") as f: json.dump(bead_data, f, indent=4)
    print(f"Created legacy bead: {bead_id}")
    return bead_id

def read_legacy_bead(bead_id):
    for directory in get_beads_dirs():
        file_path = directory / f"{bead_id}.json"
        if file_path.exists():
            with open(file_path, "r") as f: return json.load(f)
    raise FileNotFoundError(f"Legacy bead {bead_id} not found.")

def update_legacy_bead(bead_id, updates):
    for directory in get_beads_dirs():
        file_path = directory / f"{bead_id}.json"
        if file_path.exists():
            with open(file_path, "r") as f: data = json.load(f)
            data.update(updates)
            data["updated_at"] = datetime.utcnow().isoformat()
            with open(file_path, "w") as f: json.dump(data, f, indent=4)
            print(f"Updated legacy bead: {bead_id}")
            return data
    raise FileNotFoundError(f"Legacy bead {bead_id} not found.")

def upload_attachment(bead_id, file_path):
    """Uploads a file as an attachment to a Vikunja task."""
    if not str(bead_id).isdigit() or not os.path.exists(file_path):
        print(f"Skipping attachment: Bead ID {bead_id} is not Vikunja-native or file missing.")
        return

    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}/attachments"
    # Note: We do NOT send Content-Type: application/json for multipart uploads
    headers = {"Authorization": f"Bearer {VIKUNJA_API_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            with httpx.Client() as client:
                response = client.put(url, headers=headers, files=files)
                response.raise_for_status()
                print(f"Uploaded attachment {file_path} to Vikunja bead {bead_id}")
    except Exception as e:
        print(f"Failed to upload attachment: {e}")

def add_comment(bead_id, comment_text):
    """Adds a comment to a Vikunja task with an AGENT signature."""
    if not str(bead_id).isdigit():
        print(f"Skipping comment: Bead ID {bead_id} is not Vikunja-native.")
        return

    # Add signature to break webhook feedback loops
    signed_comment = f"{comment_text}\n\n[AGENT_SIGNATURE]"
    
    url = f"{VIKUNJA_BASE_URL}/tasks/{bead_id}/comments"
    headers = {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"comment": signed_comment}
    
    try:
        with httpx.Client() as client:
            response = client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Added comment to Vikunja bead {bead_id}")
    except Exception as e:
        print(f"Failed to add comment: {e}")

def link_beads(parent_id, child_id, relation_kind="subtask"):
    """Creates a relationship between two Vikunja tasks."""
    if not str(parent_id).isdigit() or not str(child_id).isdigit():
        print(f"Skipping link: Task IDs must be Vikunja-native (integers).")
        return

    url = f"{VIKUNJA_BASE_URL}/tasks/{parent_id}/relations"
    headers = {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "other_task_id": int(child_id),
        "relation_kind": relation_kind
    }
    
    try:
        with httpx.Client() as client:
            response = client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Linked bead {child_id} to {parent_id} as {relation_kind}")
    except Exception as e:
        print(f"Failed to link beads: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for b in list_beads():
            print(f"[{b['status'].upper()}] {b['id']}: {b['title']}")
