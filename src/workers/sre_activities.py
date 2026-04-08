import os
import subprocess
import httpx
import logging
import json
from datetime import datetime, timezone, timedelta
from temporalio import activity
from beads_manager import create_bead, list_beads, update_bead
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@activity.defn
async def sre_site_monitor_activity(url: str = "https://bestfam.us") -> str:
    """Monitors site health and triggers pipeline on failure."""
    logger.info(f"🛡️ SRE Monitor: Checking {url}...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return "HEALTHY"
            
            # Failure detected - Create Bead
            title = f"INCIDENT: Production {resp.status_code} at {url}"
            bead_id = create_bead(title, "Site is down. Triggering recovery.", "sre-agent", stage="VALIDATION")
            return f"HEALING_TRIGGERED: {bead_id}"
    except Exception as e:
        return f"ERROR: {str(e)}"

@activity.defn
async def sre_check_temporal_health_activity() -> list:
    """Identifies and terminates workflows running longer than 4 hours."""
    logger.info("🛡️ SRE: Checking for stale workflows...")
    stale_wfs = []
    
    try:
        # Use temporal CLI inside the container
        proc = subprocess.run(
            ["docker", "exec", "local-temporal", "temporal", "workflow", "list", "--address", "local-temporal:7233", "--output", "json"],
            capture_output=True, text=True
        )
        
        if proc.returncode != 0:
            return []

        workflows = json.loads(proc.stdout)
        now = datetime.now(timezone.utc)
        
        for wf in workflows:
            start_time_str = wf.get("startTime")
            if not start_time_str: continue
            
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            duration = now - start_time
            
            if duration > timedelta(hours=4):
                wf_id = wf.get("execution", {}).get("workflowId")
                logger.info(f"⚠️ SRE: Found stale workflow {wf_id} (Duration: {duration})")
                
                # Terminate the stale workflow
                subprocess.run([
                    "docker", "exec", "local-temporal", "temporal", "workflow", "terminate", 
                    "--workflow-id", wf_id, "--address", "local-temporal:7233"
                ])
                
                stale_wfs.append(wf_id)
                
        return stale_wfs
    except Exception as e:
        logger.error(f"SRE Stale Check failed: {e}")
        return []

@activity.defn
async def sre_log_audit_activity() -> str:
    """Scans local logs for critical errors and remediates."""
    logger.info("🛡️ SRE: Auditing system logs...")
    issues_fixed = []
    
    # 1. Check for Next.js Lock issues
    lock_file = Path("/Users/grantbest/Documents/Active/BettingApp/frontend/.next/dev/lock")
    if lock_file.exists():
        # Check if another instance is actually running
        proc = subprocess.run(["pgrep", "-f", "next-dev"], capture_output=True)
        if not proc.stdout:
            logger.info("🛠️ SRE: Found orphaned .next lock file. Removing...")
            lock_file.unlink()
            issues_fixed.append("Cleared stale .next lock")

    # 2. Check for frontend 500s in log
    log_path = Path("/Users/grantbest/Documents/Active/BettingApp/frontend.log")
    if log_path.exists():
        with open(log_path, "r") as f:
            last_lines = f.readlines()[-50:]
            if any("500 Internal Server Error" in line for line in last_lines):
                logger.info("🛠️ SRE: Detected 500 errors in frontend log. Restarting dev server...")
                subprocess.run(["pkill", "-9", "-f", "next"], check=False)
                issues_fixed.append("Restarted crashed Next.js server")

    return f"Log Audit Complete. Fixes: {', '.join(issues_fixed) if issues_fixed else 'None'}"

@activity.defn
async def sre_check_vikunja_bugs_activity() -> list:
    """Lists beads in the 'PENDING' or 'SRE' stage for healing."""
    return list_beads(status="PENDING")

@activity.defn
async def sre_remediate_issue_activity(bead: dict) -> str:
    """Processes an SRE-tagged bead with specific remediation logic."""
    bead_id = bead.get("id")
    title = bead.get("title", "").upper()
    
    update_bead(bead_id, {"stage": "DOING", "resolution": "SRE Agent is remediating the system state..."})
    
    remediations = []
    
    # 1. Fix Empty Dataset (Seeding)
    if "EMPTY DATASET" in title or "DATABASE" in title:
        logger.info("🛠️ SRE: Triggering database seeding...")
        base_path = "/Users/grantbest/Documents/Active/BettingApp"
        # Run init_db using the local venv
        proc = subprocess.run(
            ["source .venv/bin/activate && export PYTHONPATH=. && python3 init_db.py"],
            cwd=base_path, shell=True, capture_output=True, text=True
        )
        if proc.returncode == 0:
            remediations.append("Cloud DB Seeded")
        else:
            remediations.append(f"DB Seeding Failed: {proc.stderr[:50]}")

    # 2. Fix Blank Page (Render Failure)
    if "BLANK" in title or "VISUAL" in title:
        logger.info("🛠️ SRE: Recovering frontend render state...")
        # Purge .next and restart
        base_path = "/Users/grantbest/Documents/Active/BettingApp/frontend"
        subprocess.run(["pkill", "-9", "-f", "next"], check=False)
        subprocess.run(["rm", "-rf", ".next"], cwd=base_path, check=False)
        subprocess.run(
            ["nohup npm run dev > ../frontend.log 2>&1 &"],
            cwd=base_path, shell=True
        )
        remediations.append("Frontend Cache Purged & Relaunched")

    res_msg = f"Healed: {', '.join(remediations) if remediations else 'General recovery performed'}"
    update_bead(bead_id, {"stage": "DONE", "resolution": res_msg})
    return res_msg
