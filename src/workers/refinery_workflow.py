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

@activity.defn
async def check_evidence_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY GATE: Verifies that the Polecat provided test evidence.
    """
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    worktree_path = bead_data.get("context", {}).get("worktree")

    if not worktree_path:
        return "FAILED: No worktree context found."

    evidence_path = os.path.join(worktree_path, "tests", "evidence", bead_id, "pytest_output.txt")
    
    if not os.path.exists(evidence_path):
        logger.error(f"❌ Refinery: Evidence MISSING for Bead {bead_id} at {evidence_path}")
        add_comment(bead_id, "🚨 **Evidence Gate Failed:** I cannot find the `pytest_output.txt` in the evidence directory. The Polecat may have failed to run tests.")
        return "FAILED: Evidence file missing."

    # Check if file is non-empty
    if os.path.getsize(evidence_path) < 10:
        logger.error(f"❌ Refinery: Evidence EMPTY for Bead {bead_id}")
        return "FAILED: Evidence file is empty."

    logger.info(f"✅ Refinery: Evidence Gate passed for Bead {bead_id}")
    return "SUCCESS: Evidence verified."

@activity.defn
async def lint_and_format_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY GATE: Runs Ruff to lint and format the Polecat's code.
    """
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    worktree_path = bead_data.get("context", {}).get("worktree")

    if not worktree_path or not os.path.exists(worktree_path):
        return "SKIPPED: No worktree found."

    logger.info(f"🧹 Refinery: Linting code in {worktree_path}")
    
    # 1. Try to auto-fix issues
    ruff_bin = shutil.which("ruff") or "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/ruff"

    # Fix
    subprocess.run([ruff_bin, "check", "--fix", worktree_path], capture_output=True)
    # Format
    subprocess.run([ruff_bin, "format", worktree_path], capture_output=True)

    # 2. Final Check (no-fix)
    check_proc = subprocess.run([ruff_bin, "check", worktree_path], capture_output=True, text=True)
    
    if check_proc.returncode != 0:
        error_report = check_proc.stdout or check_proc.stderr
        logger.error(f"❌ Refinery: Linting FAILED for Bead {bead_id}")
        add_comment(bead_id, f"🚨 **Linting Gate Failed:** Please fix the following issues before merging:\n```\n{error_report}\n```")
        return f"FAILED: Linting errors detected.\n{error_report}"

    logger.info(f"✅ Refinery: Code quality check passed for Bead {bead_id}")
    return "SUCCESS: Code is clean and formatted."

@activity.defn
async def integration_test_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY GATE: Runs the project test suite after merge.
    """
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    base_repo_path = bead_data.get("context", {}).get("base_repo")

    if not base_repo_path:
        return "ERROR: Base repo path not found in context."

    logger.info(f"🧪 Refinery: Running integration tests in {base_repo_path}")
    
    # We use pytest from our venv
    pytest_bin = shutil.which("pytest") or "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/pytest"
    
    # Run tests
    test_proc = subprocess.run(
        [pytest_bin, "."], 
        cwd=base_repo_path,
        capture_output=True, 
        text=True
    )
    
    if test_proc.returncode != 0:
        logger.error(f"❌ Refinery: Integration Tests FAILED for Bead {bead_id}")
        add_comment(bead_id, f"🚨 **Integration Crucible Failed:** The merged code broke the test suite.\n```\n{test_proc.stdout}\n```")
        return f"FAILED: Integration tests failed.\n{test_proc.stdout}"

    logger.info(f"✅ Refinery: Integration tests passed for Bead {bead_id}")
    return "SUCCESS: All tests passed."

@activity.defn
async def rollback_merge_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY: Reverts the merge if tests fail.
    """
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    base_repo_path = bead_data.get("context", {}).get("base_repo")

    logger.warning(f"🔙 Refinery: Rolling back merge for Bead {bead_id}")
    subprocess.run(["git", "-C", base_repo_path, "reset", "--hard", "HEAD~1"], check=True)
    add_comment(bead_id, "🔙 **Refinery Update:** I have automatically rolled back the merge to keep `main` stable.")
    return "ROLLBACK_COMPLETE"

@activity.defn
async def refine_and_merge_activity(bead_id: str) -> str:
    """
    GASTOWN REFINERY: Merges a Polecat's isolated branch back into main.
    """
    from beads_manager import read_bead, update_bead, add_comment
    
    bead_data = read_bead(bead_id)
    context = bead_data.get("context", {})
    branch_name = context.get("branch")
    base_repo_path = context.get("base_repo")
    worktree_path = context.get("worktree")

    if not branch_name or not base_repo_path:
        raise ValueError(f"Refinery Error: Missing context for Bead {bead_id}")

    logger.info(f"🏗️ Refinery: Processing merge for {branch_name} in {base_repo_path}")

    try:
        # 1. Ensure the base repo is on main and clean
        subprocess.run(["git", "-C", base_repo_path, "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", base_repo_path, "pull", "origin", "main"], check=False)

        # 2. Merge the Polecat branch (it exists in the base repo too)
        logger.info(f"🏗️ Refinery: Merging {branch_name} into main at {base_repo_path}")
        merge_proc = subprocess.run(
            ["git", "-C", base_repo_path, "merge", "--no-ff", "-m", f"Refinery: Integrate Bead {bead_id}", branch_name],
            capture_output=True, text=True
        )

        if merge_proc.returncode != 0:
            logger.error(f"🏗️ Refinery: Merge CONFLICT in Bead {bead_id}")
            update_bead(bead_id, {"status": "conflicted"})
            return f"FAILED: Merge conflict in {bead_id}"

        # 3. GASTOWN DEPOSIT: Ensure changes are pushed/landed locally
        logger.info("🏗️ Refinery: Landing changes in base repository...")
        subprocess.run(["git", "-C", base_repo_path, "push", "origin", "main"], check=False) # Land on remote if exists
        
        return "MERGE_SUCCESS"
    except Exception as e:
        return f"ERROR: {str(e)}"

@activity.defn
async def cleanup_refinery_activity(bead_id: str, success: bool = True) -> str:
    """
    GASTOWN REFINERY: Cleans up the worktree and branch.
    """
    from beads_manager import read_bead, update_bead, add_comment
    bead_data = read_bead(bead_id)
    context = bead_data.get("context", {})
    branch_name = context.get("branch")
    base_repo_path = context.get("base_repo")
    worktree_path = context.get("worktree")

    if not worktree_path or not os.path.exists(worktree_path):
        return "CLEANUP_SKIPPED"

    logger.info(f"🏗️ Refinery: Cleaning up worktree {worktree_path}")
    subprocess.run(["git", "-C", base_repo_path, "worktree", "remove", "-f", worktree_path], check=False)
    subprocess.run(["git", "-C", base_repo_path, "branch", "-D", branch_name], check=False)

    if success:
        update_bead(bead_id, {"status": "completed", "done": True})
        add_comment(bead_id, f"✅ **Refinery Success:** Changes from `{branch_name}` integrated. [AGENT_SIGNATURE]")
        from beads_manager import move_to_bucket
        move_to_bucket(bead_id, "Done")
    
    return "CLEANUP_COMPLETE"

@activity.defn
async def create_gate_failure_bug_activity(bead_id: str, error_report: str, gate_type: str) -> str:
    """
    GASTOWN SRE FALLBACK: Creates a bug bead linked to the failing feature.
    """
    from beads_manager import create_bead, read_bead, link_beads, add_comment
    original_bead = read_bead(bead_id)
    
    bug_title = f"[BUG] {gate_type} Failure: {original_bead.get('title')}"
    bug_desc = f"The {gate_type} gate failed for task #{original_bead.get('index')}.\n\n**Error Report:**\n```\n{error_report}\n```"
    
    bug_id = create_bead(
        title=bug_title,
        description=bug_desc,
        requesting_agent="refinery-sre-fallback"
    )
    
    link_beads(bead_id, bug_id, relation_kind="subtask")
    add_comment(bead_id, f"🚨 **SRE Alert:** {gate_type} failed. Created linked bug task #{bug_id}.")
    return f"SRE Bug Created: {bug_id}"

@activity.defn
async def broadcast_status_activity(bead_id: str, message: str, level: str = "INFO") -> None:
    """
    GASTOWN BROADCASTER: Sends immediate updates to the user via logs and Vikunja comments.
    """
    from beads_manager import add_comment, read_bead
    
    icon = "ℹ️"
    if level == "SUCCESS": icon = "✅"
    if level == "WARNING": icon = "⚠️"
    if level == "ERROR": icon = "🚨"
    
    full_message = f"{icon} **Refinery Broadcast:** {message}"
    logger.info(f"📣 {full_message}")
    
    # Also add as a comment to the bead for dashboard visibility
    try:
        add_comment(bead_id, full_message)
    except Exception as e:
        logger.error(f"Failed to broadcast to Vikunja: {e}")

@workflow.defn
class RefineryWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Starting Integration Crucible..."],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # 0. EVIDENCE GATE
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Running Evidence Gate..."],
            start_to_close_timeout=timedelta(seconds=30)
        )
        evidence_result = await workflow.execute_activity(
            check_evidence_activity,
            bead_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry
        )
        
        if evidence_result.startswith("FAILED"):
            await workflow.execute_activity(
                broadcast_status_activity, 
                args=[bead_id, "Evidence Gate Failed. Rejecting work.", "ERROR"],
                start_to_close_timeout=timedelta(seconds=30)
            )
            await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, False], start_to_close_timeout=timedelta(minutes=5))
            return evidence_result

        # 1. QUALITY GATE
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Running Linting & Formatting Gate..."],
            start_to_close_timeout=timedelta(seconds=30)
        )
        quality_result = await workflow.execute_activity(
            lint_and_format_activity,
            bead_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry
        )
        
        if quality_result.startswith("FAILED"):
            await workflow.execute_activity(
                broadcast_status_activity, 
                args=[bead_id, "Linting Failed. Creating SRE Bug.", "ERROR"],
                start_to_close_timeout=timedelta(seconds=30)
            )
            await workflow.execute_activity(create_gate_failure_bug_activity, args=[bead_id, quality_result, "Linting"], start_to_close_timeout=timedelta(minutes=2))
            await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, False], start_to_close_timeout=timedelta(minutes=5))
            return quality_result

        # 2. INTEGRATION
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Code Quality Passed. Merging to main...", "SUCCESS"],
            start_to_close_timeout=timedelta(seconds=30)
        )
        merge_result = await workflow.execute_activity(refine_and_merge_activity, bead_id, start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)
        
        if merge_result.startswith("FAILED") or merge_result.startswith("ERROR"):
            await workflow.execute_activity(
                broadcast_status_activity,
                args=[bead_id, f"Merge Failed: {merge_result}", "ERROR"],
                start_to_close_timeout=timedelta(seconds=30)
            )
            await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, False], start_to_close_timeout=timedelta(minutes=5))
            return merge_result

        # 3. CRUCIBLE
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Merge successful. Running Integration Test Suite..."],
            start_to_close_timeout=timedelta(seconds=30)
        )
        test_result = await workflow.execute_activity(integration_test_activity, bead_id, start_to_close_timeout=timedelta(minutes=15), retry_policy=retry)

        if test_result.startswith("FAILED"):
            await workflow.execute_activity(
                broadcast_status_activity,
                args=[bead_id, "Integration Tests Failed. Rolling back merge.", "ERROR"],
                start_to_close_timeout=timedelta(seconds=30)
            )
            await workflow.execute_activity(rollback_merge_activity, bead_id, start_to_close_timeout=timedelta(minutes=2))
            await workflow.execute_activity(create_gate_failure_bug_activity, args=[bead_id, test_result, "Integration Testing"], start_to_close_timeout=timedelta(minutes=2))
            await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, False], start_to_close_timeout=timedelta(minutes=5))
            return test_result

        # 5. FINALIZATION
        await workflow.execute_activity(
            broadcast_status_activity,
            args=[bead_id, "Crucible Passed. Finalizing integration.", "SUCCESS"],
            start_to_close_timeout=timedelta(seconds=30)
        )
        return await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, True], start_to_close_timeout=timedelta(minutes=5))
