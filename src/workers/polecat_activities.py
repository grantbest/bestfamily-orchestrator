import os
import subprocess
import shutil
import logging
from typing import List, Optional, Dict, Any

try:
    from temporalio import activity
except ImportError:
    # Fallback for testing/CLI
    class activity:
        @staticmethod
        def defn(func): return func
        @staticmethod
        def heartbeat(*args): pass

# Setup logging
logger = logging.getLogger(__name__)

# --- DEVELOPER AGENT ACTIVITIES ---

@activity.defn
async def polecat_developer_activity(bead_id: str) -> str:
    """
    🐾 Polecat: The Developer Agent Activity.
    GASTOWN RESILIENCY: Heartbeating enabled for long LLM runs.
    """
    from src.agents.developer import DeveloperAgent
    from beads_manager import read_bead, update_bead
    
    logger.info(f"🐾 Polecat: Starting implementation for Bead {bead_id}")
    
    # 1. Fetch Bead Context
    bead_data = read_bead(bead_id)
    if not bead_data:
        return f"ERROR: Bead {bead_id} not found."

    # 2. Setup Isolation
    isolation_root = "/tmp/polecats"
    worktree_path = f"{isolation_root}/polecat-{bead_id}"
    base_repo_path = "/Users/grantbest/Documents/Active/BettingApp" # Default
    
    if "homelab" in bead_data['title'].lower() or "infrastructure" in bead_data['title'].lower():
        base_repo_path = "/Users/grantbest/Documents/Active/Homelab"

    branch_name = f"polecat/{bead_id}"
    
    try:
        # HEARTBEAT: Initial state
        activity.heartbeat("Preparing Git worktree")
        
        # SRE: Aggressive cleanup
        subprocess.run(["git", "-C", base_repo_path, "worktree", "prune"], check=False)

        if os.path.exists(worktree_path):
            logger.info(f"🐾 Polecat: Cleaning up stale worktree at {worktree_path}")
            subprocess.run(["git", "-C", base_repo_path, "worktree", "remove", "-f", worktree_path], check=False, capture_output=True)
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path, ignore_errors=True)

        logger.info(f"🐾 Polecat: Ensuring branch {branch_name} is clean")
        subprocess.run(["git", "-C", base_repo_path, "branch", "-D", branch_name], check=False, capture_output=True)

        # Create Worktree
        logger.info(f"🐾 Polecat: Creating worktree and branch {branch_name}")
        subprocess.run(
            ["git", "-C", base_repo_path, "worktree", "add", "-b", branch_name, worktree_path, "main"], 
            check=True, capture_output=True, text=True
        )

        # 3. Initialize Agent
        activity.heartbeat(f"Implementing via Gemma 4 (Task: {bead_data['title']})")
        
        agent = DeveloperAgent(worktree_path)
        
        # SRE: Update bead with context for Refinery
        update_bead(bead_id, {
            "stage": "DOING",
            "context": {
                "branch": branch_name,
                "worktree": worktree_path,
                "base_repo": base_repo_path
            }
        })

        # 4. RUN IMPLEMENTATION (The long pole)
        # SRE: Use the correct method name 'implement_feature'
        result = await agent.implement_feature(bead_data['title'], bead_data['description'], files=[], bead_id=bead_id)
        
        activity.heartbeat("Implementation complete, pushing changes...")
        
        # 5. Commit changes to the branch
        subprocess.run(["git", "-C", worktree_path, "add", "."], check=False)
        subprocess.run(["git", "-C", worktree_path, "commit", "-m", f"Polecat: Implementation for Bead {bead_id}"], capture_output=True)
        subprocess.run(["git", "-C", worktree_path, "push", "origin", branch_name], check=False)

        update_bead(bead_id, {"stage": "VALIDATION", "resolution": result})
        return result

    except Exception as e:
        error_msg = f"Polecat GIT ERROR: {str(e)}"
        if hasattr(e, 'stderr') and e.stderr:
            error_msg += f"\nSTDERR: {e.stderr}"
        logger.error(error_msg)
        update_bead(bead_id, {"stage": "DOING", "resolution": error_msg})
        return error_msg
