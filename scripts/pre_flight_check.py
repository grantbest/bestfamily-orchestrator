import sys
import os
import logging
from importlib import import_module

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PreFlight")

def check_imports():
    """Verify that all critical components are importable."""
    modules_to_test = [
        "beads_manager",
        "src.utils.model_router",
        "src.workers.unified_orchestrator",
        "src.workers.pipeline_workflow",
        "src.workers.mayor_workflow",
        "src.workers.refinery_workflow",
        "src.workers.polecat_activities"
    ]
    
    # Add paths to sys.path
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.append(workspace_root)
    sys.path.append(os.path.join(workspace_root, "scripts"))
    sys.path.append(os.path.join(workspace_root, "src"))

    failed = False
    for mod in modules_to_test:
        try:
            import_module(mod)
            logger.info(f"✅ Import successful: {mod}")
        except ImportError as e:
            logger.error(f"❌ Import FAILED: {mod} - {e}")
            failed = True
        except Exception as e:
            logger.error(f"❌ Unexpected error importing {mod}: {e}")
            failed = True
            
    return not failed

def check_env():
    """Check if critical environment variables are set."""
    required_vars = ["VIKUNJA_API_TOKEN", "TEMPORAL_ADDRESS"]
    # Model keys are optional as we have fallback to Ollama
    
    # Try loading env first via beads_manager
    try:
        from beads_manager import VIKUNJA_API_TOKEN as token
        if token: logger.info("✅ VIKUNJA_API_TOKEN is loaded.")
        else: logger.warning("⚠️ VIKUNJA_API_TOKEN is empty.")
    except Exception as e:
        logger.error(f"❌ Failed to check VIKUNJA_API_TOKEN: {e}")

    failed = False
    for var in required_vars:
        if not os.getenv(var) and var != "VIKUNJA_API_TOKEN": # Already checked via beads_manager
             logger.warning(f"⚠️ Environment variable {var} is not set. Using defaults.")
             
    return not failed

if __name__ == "__main__":
    logger.info("🧪 STARTING AGENT PRE-FLIGHT CHECK...")
    
    imports_ok = check_imports()
    env_ok = check_env()
    
    if imports_ok and env_ok:
        logger.info("🟢 PRE-FLIGHT CHECK PASSED. Agents are ready to launch.")
        sys.exit(0)
    else:
        logger.error("🔴 PRE-FLIGHT CHECK FAILED.")
        sys.exit(1)
