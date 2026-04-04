import os
import subprocess
import httpx
import logging
from temporalio import activity
from beads_manager import create_bead

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@activity.defn
async def sre_site_monitor_activity(url: str = "https://bestfam.us") -> str:
    """
    GASTOWN SRE: Monitors the production site and triggers a heal if 404/failure detected.
    """
    logger.info(f"🛡️ SRE Monitor: Checking health of {url}...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                logger.info(f"✅ SRE Monitor: {url} is healthy (200 OK)")
                return "HEALTHY"
            else:
                error_msg = f"🚨 SRE ALERT: {url} returned {response.status_code}!"
                logger.error(error_msg)
                
                # 1. Create a "Heal" Bead
                bead_id = create_bead(
                    title=f"AUTOMATED HEAL: Production Outage Detected ({response.status_code})",
                    description=f"The site {url} is down. SRE Agent is triggering an automated pipeline restoration.",
                    requesting_agent="sre-monitor"
                )
                
                # 2. Trigger the Pipeline restoration
                # SRE Fix: Use absolute path and explicit working directory
                base_path = "/Users/grantbest/Documents/Active/Homelab"
                pipeline_script = os.path.join(base_path, "pipeline.sh")
                
                logger.info(f"🛠️ SRE Monitor: Triggering restoration pipeline at {pipeline_script}")
                
                # Run pipeline in background with correct CWD
                subprocess.Popen(
                    [pipeline_script], 
                    cwd=base_path,
                    start_new_session=True
                )
                
                return f"HEALING_TRIGGERED: Bead {bead_id}"

    except Exception as e:
        logger.error(f"🚨 SRE Monitor: Connection error to {url}: {e}")
        return f"CRITICAL_FAILURE: {str(e)}"
