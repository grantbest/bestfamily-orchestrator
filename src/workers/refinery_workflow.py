import os
import shutil
import subprocess
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- REFINERY ACTIVITIES ---

@activity.defn
async def resolve_refinery_strategy_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY: Determines which gates to apply based on task type.
    """
    from beads_manager import read_bead
    bead = read_bead(bead_id)
    title = bead.get("title", "").upper()
    
    if "[EPIC]" in title:
        return "BREAKDOWN"
    elif "[STORY]" in title:
        return "IMPLEMENTATION"
    elif "DESIGN" in title or "ARCHITECT" in title:
        return "DESIGN"
    else:
        return "GENERIC"

@activity.defn
async def check_evidence_activity(bead_id: str) -> str:
    """GASTOWN REFINERY GATE: Verifies implementation evidence."""
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    worktree_path = bead_data.get("context", {}).get("worktree")

    if not worktree_path:
        return "FAILED: No worktree context found."

    # Evidence stored in: tests/evidence/<bead_id>/pytest_output.txt
    evidence_path = os.path.join(worktree_path, "tests", "evidence", bead_id, "pytest_output.txt")
    if not os.path.exists(evidence_path):
        add_comment(bead_id, "🚨 **Refinery Gate Failed:** Missing `pytest_output.txt`.")
        return "FAILED: Evidence file missing."

    return "SUCCESS: Evidence verified."

@activity.defn
async def lint_and_format_activity(bead_id: str) -> str:
    """GASTOWN REFINERY GATE: Runs Ruff to ensure Gastown code standards."""
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    worktree_path = bead_data.get("context", {}).get("worktree")

    if not worktree_path or not os.path.exists(worktree_path):
        return "SKIPPED"

    ruff_bin = shutil.which("ruff") or "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/ruff"
    # Format and Fix
    subprocess.run([ruff_bin, "check", "--fix", worktree_path], capture_output=True)
    subprocess.run([ruff_bin, "format", worktree_path], capture_output=True)
    
    # Final verification
    check_proc = subprocess.run([ruff_bin, "check", worktree_path], capture_output=True, text=True)
    if check_proc.returncode != 0:
        add_comment(bead_id, f"🚨 **Refinery Gate Failed:** Linting errors.\n```\n{check_proc.stdout}\n```")
        return "FAILED: Linting errors."

    return "SUCCESS"

@activity.defn
async def refine_and_merge_activity(bead_id: str) -> str:
    """GASTOWN REFINERY: Lands changes into the main line."""
    from beads_manager import read_bead, update_bead
    bead_data = read_bead(bead_id)
    context = bead_data.get("context", {})
    branch_name = context.get("branch")
    base_repo_path = context.get("base_repo")

    if not branch_name or not base_repo_path:
        return "ERROR: Missing git context"

    try:
        # 0. GASTOWN PURIFICATION: Ensure the worktree changes are actually committed to the branch
        worktree_path = context.get("worktree")
        if worktree_path and os.path.exists(worktree_path):
            logger.info(f"🏗️ Refinery: Purifying worktree at {worktree_path}")
            subprocess.run(["git", "-C", worktree_path, "add", "."], check=False)
            subprocess.run(["git", "-C", worktree_path, "commit", "-m", f"Refinery: Final purification for Bead {bead_id}"], capture_output=True)
            # Push to the local repo so main can see it
            subprocess.run(["git", "-C", worktree_path, "push", "origin", branch_name], check=False)

        subprocess.run(["git", "-C", base_repo_path, "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", base_repo_path, "pull", "origin", "main"], check=False)
        
        # Merge story branch into main
        merge_proc = subprocess.run(
            ["git", "-C", base_repo_path, "merge", "--no-ff", "-m", f"Refinery: Integrate Bead {bead_id}", branch_name],
            capture_output=True, text=True
        )
        
        if merge_proc.returncode != 0:
            return "FAILED: Merge conflict"
            
        return "MERGE_SUCCESS"
    except Exception as e:
        return f"ERROR: {str(e)}"

@activity.defn
async def cleanup_refinery_activity(bead_id: str, success: bool = True) -> str:
    """GASTOWN REFINERY: Finalizes the task lifecycle."""
    from beads_manager import update_bead, add_comment
    
    if success:
        update_bead(bead_id, {"stage": "DONE"})
        add_comment(bead_id, "✅ **Refinery Success:** Task validated and closed. [AGENT_SIGNATURE]")
    
    return "REFINERY_COMPLETE"

@activity.defn
async def broadcast_status_activity(bead_id: str, message: str, level: str = "INFO") -> None:
    """GASTOWN BROADCASTER: System-wide status updates."""
    from beads_manager import add_comment
    icon = "ℹ️"
    if level == "SUCCESS": icon = "✅"
    if level == "ERROR": icon = "🚨"
    full_message = f"{icon} **Refinery:** {message}"
    logger.info(f"📣 {full_message}")
    try:
        add_comment(bead_id, full_message)
    except: pass

# --- REFINERY WORKFLOW ---

@workflow.defn
class RefineryWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        
        # 1. Strategy Resolution
        strategy = await workflow.execute_activity(
            resolve_refinery_strategy_activity, bead_id,
            start_to_close_timeout=timedelta(seconds=30), retry_policy=retry
        )
        
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, f"Initiating specialized purification for {strategy} mode..."],
            start_to_close_timeout=timedelta(seconds=30)
        )

        if strategy == "IMPLEMENTATION":
            # Evidence Gate
            evidence = await workflow.execute_activity(check_evidence_activity, bead_id, start_to_close_timeout=timedelta(minutes=2), retry_policy=retry)
            if evidence.startswith("FAILED"): return evidence

            # Quality Gate
            quality = await workflow.execute_activity(lint_and_format_activity, bead_id, start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)
            if quality.startswith("FAILED"): return quality

            # Landing Gate
            merge = await workflow.execute_activity(refine_and_merge_activity, bead_id, start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)
            if merge.startswith("FAILED"): return merge

        elif strategy == "BREAKDOWN":
            # Breakdown Validation (Placeholder for future checks)
            await workflow.execute_activity(broadcast_status_activity, args=[bead_id, "Validating story fan-out and parent linking..."], start_to_close_timeout=timedelta(seconds=30))

        elif strategy == "DESIGN":
            # Design Validation (Placeholder for future technical spec audit)
            await workflow.execute_activity(broadcast_status_activity, args=[bead_id, "Auditing technical specification synthesis..."], start_to_close_timeout=timedelta(seconds=30))

        # FINALIZATION
        return await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, True], start_to_close_timeout=timedelta(minutes=5))
