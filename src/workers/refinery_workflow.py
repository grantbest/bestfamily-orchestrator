import os
import shutil
import subprocess
import logging
import asyncio
import json
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

# Setup logging
logger = logging.getLogger(__name__)

# --- REFINERY v3.4 ACTIVITIES ---

@activity.defn
async def data_integrity_audit_activity(bead_id: str) -> str:
    """GASTOWN REFINERY GATE: Deep data inspection. Ensures APIs aren't returning empty arrays."""
    import httpx
    from beads_manager import add_comment
    logger.info(f"Refinery[{bead_id}]: Starting Data Integrity Audit...")
    
    endpoints = {
        "Bets": "http://localhost:3000/api/bets",
        "Teams": "http://localhost:3000/api/teams",
        "Config": "http://localhost:3000/api/config"
    }
    results = []
    failed = False

    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, url in endpoints.items():
            try:
                resp = await client.get(url)
                data = resp.json()
                logger.info(f"Refinery[{bead_id}]: Checking {name} -> Status: {resp.status_code}")
                
                if name == "Config":
                    if data.get("appEnv") == "production":
                        results.append(f"✅ {name}: Aligned to Production")
                    else:
                        results.append(f"🚨 {name}: DRIFT DETECTED (Env: {data.get('appEnv')})")
                        failed = True
                else:
                    count = len(data) if isinstance(data, list) else 0
                    if count > 0:
                        results.append(f"✅ {name}: {count} records found")
                    else:
                        results.append(f"❌ {name}: EMPTY DATASET DETECTED")
                        failed = True
            except Exception as e:
                logger.error(f"Refinery[{bead_id}]: Error checking {name}: {e}")
                results.append(f"❌ {name}: API Error ({str(e)})")
                failed = True

    summary = "\n".join(results)
    add_comment(bead_id, f"### 📊 Data Integrity Audit\n{summary}")
    
    if failed:
        logger.error(f"Refinery[{bead_id}]: Data Integrity Audit FAILED\n{summary}")
        return f"FAILED: Data integrity check failed.\n{summary}"
    
    logger.info(f"Refinery[{bead_id}]: Data Integrity Audit PASSED")
    return "SUCCESS"

@activity.defn
async def playwright_e2e_audit_activity(bead_id: str) -> str:
    """GASTOWN REFINERY GATE: Visual 'Proof of Life'. Uses Playwright to detect blank pages."""
    from beads_manager import add_comment
    logger.info(f"Refinery[{bead_id}]: Starting Playwright Visual Audit...")
    
    test_script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {{
    await page.goto('http://localhost:3000', {{ waitUntil: 'networkidle' }});
    const title = await page.title();
    const hasHeader = await page.getByText('BestFam Live Dashboard').isVisible();
    const noDataVisible = await page.getByText('No data.').isVisible();
    const loadingVisible = await page.getByText('Loading...').isVisible();
    
    if (hasHeader && !noDataVisible && !loadingVisible) {{
      console.log('RENDER_SUCCESS');
    }} else {{
      console.log('RENDER_FAILURE: Header=' + hasHeader + ', NoData=' + noDataVisible + ', Loading=' + loadingVisible);
    }}
  }} catch (e) {{
    console.log('RENDER_CRASH: ' + e.message);
  }} finally {{
    await browser.close();
  }}
}})();
"""
    # Create temp test file
    temp_test = f"/tmp/refinery_verify_{bead_id}.js"
    with open(temp_test, "w") as f:
        f.write(test_script)

    try:
        env = os.environ.copy()
        homelab_node_modules = "/Users/grantbest/Documents/Active/Homelab/node_modules"
        env["NODE_PATH"] = homelab_node_modules
        
        proc = subprocess.run(["node", temp_test], capture_output=True, text=True, timeout=60, env=env)
        output = proc.stdout.strip()
        error_output = proc.stderr.strip()
        logger.info(f"Refinery[{bead_id}]: Playwright stdout: {output}")
        if error_output:
            logger.error(f"Refinery[{bead_id}]: Playwright stderr: {error_output}")
        
        if "RENDER_SUCCESS" in output:
            add_comment(bead_id, "✅ **Visual Proof:** Playwright confirmed dashboard is hydrated and rendering data.")
            return "SUCCESS"
        else:
            add_comment(bead_id, f"🚨 **Visual Proof FAILED:** Dashboard appears blank or broken.\nTrace: {output}")
            logger.error(f"Refinery[{bead_id}]: Playwright Visual Audit FAILED: {output}")
            return f"FAILED: Visual render failed. {output}"
    except Exception as e:
        logger.error(f"Refinery[{bead_id}]: Playwright Audit Exception: {e}")
        return f"FAILED: Playwright execution error: {str(e)}"

@activity.defn
async def pre_commit_audit_activity(bead_id: str) -> str:
    from beads_manager import read_bead, add_comment
    bead_data = read_bead(bead_id)
    worktree_path = bead_data.get("context", {}).get("worktree")
    if not worktree_path: return "SKIPPED"
    
    pre_commit_bin = "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/pre-commit"
    proc = subprocess.run([pre_commit_bin, "run", "--all-files"], cwd=worktree_path, capture_output=True, text=True)
    
    if proc.returncode != 0:
        add_comment(bead_id, f"🚨 **Security Gate Failed:** Secrets detected!\n```\n{proc.stdout}\n```")
        return "FAILED: Security audit failed."
    return "SUCCESS"

@activity.defn
async def refine_and_merge_activity(bead_id: str) -> str:
    from beads_manager import read_bead, update_bead
    bead_data = read_bead(bead_id)
    context = bead_data.get("context", {})
    branch_name = context.get("branch")
    base_repo_path = context.get("base_repo")
    worktree_path = context.get("worktree")
    if not branch_name or not base_repo_path:
        logger.warning(f"Refinery: Skipping merge for bead {bead_id} - No git context.")
        return "SKIPPED: No git context"
    try:
        if worktree_path and os.path.exists(worktree_path):
            subprocess.run(["git", "-C", worktree_path, "add", "."], check=False)
            subprocess.run(["git", "-C", worktree_path, "commit", "-m", f"Refinery: Final purification for Bead {bead_id}"], capture_output=True)
            subprocess.run(["git", "-C", worktree_path, "push", "origin", branch_name], check=False)
        subprocess.run(["git", "-C", base_repo_path, "reset", "--hard", "HEAD"], check=False)
        subprocess.run(["git", "-C", base_repo_path, "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", base_repo_path, "pull", "origin", "main"], check=False)
        merge_proc = subprocess.run(["git", "-C", base_repo_path, "merge", "--no-ff", "-m", f"Refinery: Integrate Bead {bead_id}", branch_name], capture_output=True, text=True)
        if merge_proc.returncode != 0:
            return "FAILED: Merge conflict"
        subprocess.run(["git", "-C", base_repo_path, "push", "origin", "main"], check=False)
        
        # SRE: Execute pipeline locally to fulfill "all the things the pipeline provides"
        pipeline_path = "/Users/grantbest/Documents/Active/Homelab/pipeline.sh"
        if os.path.exists(pipeline_path):
            logger.info(f"Refinery[{bead_id}]: Executing local pipeline {pipeline_path}")
            proc = subprocess.run([pipeline_path], cwd="/Users/grantbest/Documents/Active/Homelab", capture_output=True, text=True)
            if proc.returncode != 0:
                logger.error(f"Refinery[{bead_id}]: Pipeline execution failed: {proc.stdout}\n{proc.stderr}")
                return "FAILED: Pipeline execution failed"
            else:
                logger.info(f"Refinery[{bead_id}]: Pipeline execution succeeded.")
                
        return "MERGE_SUCCESS"
    except Exception as e:
        return f"ERROR: {str(e)}"

@activity.defn
async def cleanup_refinery_activity(bead_id: str, success: bool = True) -> str:
    from beads_manager import update_bead, add_comment
    if success:
        update_bead(bead_id, {"stage": "DONE"})
        add_comment(bead_id, "🏆 **Refinery v3.4 Success:** Code merged and visually verified. [AGENT_SIGNATURE]")
    return "REFINERY_COMPLETE"

@activity.defn
async def broadcast_status_activity(bead_id: str, message: str) -> None:
    from beads_manager import add_comment
    try:
        add_comment(bead_id, f"ℹ️ **Refinery:** {message}")
    except: pass

@workflow.defn(name="RefineryWorkflow")
class RefineryWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        
        # 1. Triage Strategy
        await workflow.execute_activity(broadcast_status_activity, args=[bead_id, "Initiating v3.4 'True Verification' Gate..."], start_to_close_timeout=timedelta(seconds=30))
        
        # 2. Security Audit
        security = await workflow.execute_activity(pre_commit_audit_activity, bead_id, start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)
        if security.startswith("FAILED"): return security

        # 3. Data Integrity Audit (The 'Empty Dashboard' Catch)
        data_audit = await workflow.execute_activity(data_integrity_audit_activity, bead_id, start_to_close_timeout=timedelta(minutes=2), retry_policy=retry)
        if data_audit.startswith("FAILED"): return data_audit

        # 4. Playwright Visual Audit (The 'Blank Page' Catch)
        visual_audit = await workflow.execute_activity(playwright_e2e_audit_activity, bead_id, start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)
        if visual_audit.startswith("FAILED"): return visual_audit

        # 5. Merge and Deploy
        merge_result = await workflow.execute_activity(refine_and_merge_activity, bead_id, start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)
        if merge_result.startswith("FAILED"): return merge_result

        # 6. Final Cleanup & Close
        return await workflow.execute_activity(cleanup_refinery_activity, args=[bead_id, True], start_to_close_timeout=timedelta(minutes=5))
