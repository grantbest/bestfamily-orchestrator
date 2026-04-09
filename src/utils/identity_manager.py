import os
import json
import httpx
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class IdentityManager:
    """
    SRE: Centralized session management for Vikunja.
    Ensures all Gastown processes share a single, self-healing token.
    """
    TOKEN_FILE = Path("/Users/grantbest/Documents/Active/BestFam-Orchestrator/.gastown_session.json")

    @classmethod
    def get_token(cls):
        if cls.TOKEN_FILE.exists():
            try:
                data = json.loads(cls.TOKEN_FILE.read_text())
                # Check if token is likely expired (using 10m safety margin)
                if data.get("expires_at", 0) > time.time() + 600:
                    return data.get("token")
            except:
                pass
        return cls.refresh_session()

    @classmethod
    def refresh_session(cls):
        logger.info("IdentityManager: Initiating global session refresh...")
        url = os.getenv("VIKUNJA_BASE_URL", "http://localhost:3456/api/v1")
        login_url = f"{url.split('/api/v1')[0]}/api/v1/login"
        
        try:
            with httpx.Client() as client:
                resp = client.post(
                    login_url,
                    json={"username": "admin", "password": "BestFam2026!"},
                    timeout=10.0
                )
                if resp.status_code == 200:
                    token = resp.json().get("token")
                    # SRE: Tokens usually last 15m or 1h. We set a conservative 14m TTL.
                    expires_at = time.time() + 840 
                    cls.TOKEN_FILE.write_text(json.dumps({
                        "token": token,
                        "expires_at": expires_at
                    }))
                    logger.info("IdentityManager: Global session updated.")
                    return token
        except Exception as e:
            logger.error(f"IdentityManager: Failed to refresh global session: {e}")
        return None
