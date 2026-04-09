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
    """Check if critical infrastructure is ready."""
    import httpx
    
    # SRE: Check Sidecar Gateway
    try:
        resp = httpx.get("http://localhost:8001/health", timeout=5.0)
        if resp.status_code == 200:
            logger.info("✅ Sidecar Gateway is healthy.")
            return True
        else:
            logger.error(f"❌ Sidecar Gateway returned {resp.status_code}.")
    except Exception as e:
        logger.error(f"❌ Sidecar Gateway unreachable: {e}")
             
    return False

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
