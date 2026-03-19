import os
import subprocess
import shutil
import logging

try:
    from temporalio import activity
except ImportError:
    # Fallback for testing/CLI
    class activity:
        @staticmethod
        def defn(func): return func

from src.agents.developer import DeveloperAgent
from beads_manager import read_bead, update_bead

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@activity.defn
async def polecat_developer_activity(bead_id: str) -> str:
    """
    GASTOWN POLECAT: Executes work in an isolated Git worktree.
    """
    bead_data = read_bead(bead_id)
    task_title = bead_data.get("title", "No Title")
    instruction = bead_data.get("description", "No Instructions")
    
    # --- GASTOWN TESTING CRUCIBLE (REQ-4) ---
    # Automatically append strict testing requirements to all implementation tasks.
    instruction += "\n\nSTRICT REQUIREMENT: You MUST implement or update a corresponding test file in the 'tests/' directory to verify this change. Code without tests will be rejected by the Integration Crucible."
    instruction += "\n\nSTRICT PEP 8 COMPLIANCE: Do NOT use bare 'except:' blocks. Always use 'except Exception:' or a specific exception class. Bare excepts will be rejected by the Linting Gate."
    
    # 1. Determine Repository Root (Default to BettingApp for now)
    # In a real Gastown setup, the Mayor would specify the 'Rig' (repo).
    # Using absolute paths based on the current environment.
    # Container mounts at /app/*, host path fallback for local dev
    workspace_root = os.getenv("WORKSPACE_ROOT", "/app")
    if not os.path.exists(workspace_root):
        workspace_root = "/Users/grantbest/Documents/Active"

    base_repo_path = os.path.join(workspace_root, "BettingApp")

    if "homelab" in task_title.lower() or "infrastructure" in task_title.lower():
        base_repo_path = os.path.join(workspace_root, "Homelab")
    
    # 2. Setup Isolation (Git Worktree)
    # We use a unique directory for this specific Polecat run.
    worktree_parent = "/tmp/polecats"
    os.makedirs(worktree_parent, exist_ok=True)
    worktree_path = os.path.join(worktree_parent, f"polecat-{bead_id}")
    branch_name = f"polecat/{bead_id}"
    
    logger.info(f"🐾 Polecat: Isolating work for Bead {bead_id} in {worktree_path}")
    
    try:
        # Clean up if exists (stale run)
        if os.path.exists(worktree_path):
            logger.info(f"🐾 Polecat: Cleaning up stale worktree at {worktree_path}")
            # Try to remove git worktree first
            subprocess.run(["git", "-C", base_repo_path, "worktree", "remove", "-f", worktree_path], check=False, capture_output=True)
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path)

        # Create Worktree
        # SRE: Ensure we don't fail if the branch already exists (from a previous failed attempt)
        logger.info(f"🐾 Polecat: Ensuring branch {branch_name} is clean")
        subprocess.run(["git", "-C", base_repo_path, "branch", "-D", branch_name], check=False, capture_output=True)

        # git worktree add -b <new-branch> <path> <start-point>
        logger.info(f"🐾 Polecat: Creating worktree and branch {branch_name}")
        subprocess.run(
            ["git", "-C", base_repo_path, "worktree", "add", "-b", branch_name, worktree_path, "main"], 
            check=True, capture_output=True, text=True
        )
        
        # 3. Execute Developer Agent in Worktree
        # SRE: Configure pip to use the Nexus Artifact Refinery (Proxy)
        # Using host.docker.internal to reach Nexus from a container, 
        # or localhost if running natively.
        nexus_proxy = os.getenv("PIP_INDEX_URL", "http://localhost:8082/nexus/repository/pypi-proxy/simple")
        nexus_host = "localhost" # For PIP_TRUSTED_HOST
        
        env = os.environ.copy()
        env["PIP_INDEX_URL"] = nexus_proxy
        env["PIP_TRUSTED_HOST"] = nexus_host
        
        logger.info(f"🐾 Polecat: Using Artifact Refinery at {nexus_proxy}")
        
        # Patch the agent's environment or pass it in
        agent = DeveloperAgent(workspace_root=worktree_path)
        result = await agent.implement_feature(task_title, instruction, [], bead_id=bead_id)
        
        # 4. Push Changes (to simulate external refinery integration)
        # Note: In local dev without a remote, this might be skipped or mocked.
        # logger.info(f"🐾 Polecat: Pushing changes for {branch_name}")
        # subprocess.run(["git", "-C", worktree_path, "push", "origin", branch_name], check=False)
        
        # 5. Update Bead State
        update_bead(bead_id, {
            "resolution": f"{result}\n\nBranch: {branch_name}", 
            "status": "resolved",
            "context": {
                "branch": branch_name, 
                "worktree": worktree_path,
                "base_repo": base_repo_path
            }
        })
        
        return f"Polecat Success: Changes isolated in branch {branch_name}"

    except subprocess.CalledProcessError as e:
        error_msg = f"Polecat GIT ERROR: {e.stderr}"
        logger.error(error_msg)
        update_bead(bead_id, {"status": "failed", "resolution": error_msg})
        return error_msg
    except Exception as e:
        error_msg = f"Polecat EXCEPTION: {str(e)}"
        logger.error(error_msg)
        update_bead(bead_id, {"status": "failed", "resolution": error_msg})
        return error_msg
