import sys
import os
import asyncio
import json
import shutil
import subprocess
from unittest.mock import MagicMock, patch

# Ensure we can import from src and scripts
current_dir = os.getcwd()
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "src"))
sys.path.append(os.path.join(current_dir, "scripts"))

# --- MOCKING MISSING DEPENDENCIES ---
mock_beads_manager = MagicMock()
mock_bead_id = "smoke-test-bead-123"
mock_bead_data = {
    "id": mock_bead_id,
    "title": "Smoke Test Task",
    "description": "Add a dummy file to verify worktree isolation.",
    "status": "pending",
    "context": {}
}

def mock_read_bead(bid):
    return mock_bead_data

def mock_update_bead(bid, updates):
    mock_bead_data.update(updates)
    return mock_bead_data

mock_beads_manager.read_bead = mock_read_bead
mock_beads_manager.update_bead = mock_update_bead

# Prevent imports from failing by patching sys.modules
sys.modules["beads_manager"] = mock_beads_manager
sys.modules["httpx"] = MagicMock()

async def run_smoke_test():
    print("🚀 Starting Polecat Smoke Test...")
    
    # Now we can import the activity
    from src.workers.polecat_activities import polecat_developer_activity
    
    # Mock DeveloperAgent
    with patch("src.workers.polecat_activities.DeveloperAgent") as MockAgent:
        instance = MockAgent.return_value
        # Async mock helper
        async def mock_implement(*args, **kwargs):
            return "MOCKED SUCCESS"
        instance.implement_feature = mock_implement
        
        # Set environment for paths
        os.environ["WORKSPACE_ROOT"] = current_dir.replace("/BestFam-Orchestrator", "")
        
        # Execute Activity
        result = await polecat_developer_activity(mock_bead_id)
        print(f"Result: {result}")
        
        # --- VERIFICATION ---
        
        # 1. Check if mock_bead_data was updated
        print(f"Updated Bead Context: {json.dumps(mock_bead_data.get('context'), indent=2)}")
        
        worktree_path = mock_bead_data.get("context", {}).get("worktree")
        branch_name = mock_bead_data.get("context", {}).get("branch")
        repo_path = mock_bead_data.get("context", {}).get("base_repo")
        
        if not worktree_path or not branch_name:
            print("❌ ERROR: Worktree path or Branch name missing in context.")
            return

        # 2. Verify Worktree existence
        if os.path.exists(worktree_path):
            print(f"✅ Worktree created at: {worktree_path}")
            # Check if it's a valid worktree
            wt_check = subprocess.run(["git", "-C", repo_path, "worktree", "list"], capture_output=True, text=True)
            if worktree_path in wt_check.stdout:
                print("✅ Git recognizes the worktree.")
            else:
                print("❌ Git does NOT recognize the worktree.")
        else:
            print(f"❌ Worktree directory NOT found at: {worktree_path}")
            
        # 3. Verify Git branch
        branches = subprocess.check_output(["git", "-C", repo_path, "branch"], text=True)
        if branch_name in branches:
            print(f"✅ Branch created: {branch_name}")
        else:
            print(f"❌ Branch NOT found: {branch_name}")

        # 4. Clean up
        print("🧹 Cleaning up...")
        subprocess.run(["git", "-C", repo_path, "worktree", "remove", "-f", worktree_path], check=False)
        subprocess.run(["git", "-C", repo_path, "branch", "-D", branch_name], check=False)
        
        print("🏁 Smoke Test Finished.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
