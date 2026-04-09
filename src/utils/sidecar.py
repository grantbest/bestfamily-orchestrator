import os
import json
import httpx
import logging
import time
import asyncio
from fastapi import FastAPI, Request, HTTPException
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GastownSidecar")

app = FastAPI(title="Gastown Resiliency Sidecar")

# Persistent Session Storage
TOKEN_FILE = Path("/Users/grantbest/Documents/Active/BestFam-Orchestrator/.gastown_session.json")
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")

# MACBOOK RESOURCE PROTECTION: Only 1 heavy LLM call at a time
ollama_semaphore = asyncio.Semaphore(1)

class SessionManager:
    token = None
    expires_at = 0

    @classmethod
    def get_valid_token(cls):
        if cls.token and cls.expires_at > time.time() + 300: return cls.token
        if TOKEN_FILE.exists():
            try:
                data = json.loads(TOKEN_FILE.read_text())
                if data.get("expires_at", 0) > time.time() + 300:
                    cls.token, cls.expires_at = data.get("token"), data.get("expires_at")
                    return cls.token
            except: pass
        return cls.refresh()

    @classmethod
    def refresh(cls):
        logger.info("Sidecar: Refreshing Vikunja session...")
        login_url = f"{VIKUNJA_BASE_URL.split('/api/v1')[0]}/api/v1/login"
        try:
            with httpx.Client() as client:
                resp = client.post(login_url, json={"username": "admin", "password": "BestFam2026!"}, timeout=10.0)
                if resp.status_code == 200:
                    cls.token = resp.json().get("token")
                    cls.expires_at = time.time() + 840
                    TOKEN_FILE.write_text(json.dumps({"token": cls.token, "expires_at": cls.expires_at}))
                    return cls.token
        except Exception as e: logger.error(f"Sidecar: Auth failed: {e}")
        return None

@app.get("/health")
async def health():
    return {"status": "ok", "auth_valid": SessionManager.get_valid_token() is not None}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_vikunja(path: str, request: Request):
    """Resilient Proxy for Vikunja API."""
    token = SessionManager.get_valid_token()
    if not token: raise HTTPException(status_code=503, detail="Vikunja Authentication Unavailable")

    url = f"{VIKUNJA_BASE_URL}/{path}"
    if request.query_params: url += f"?{request.query_params}"

    method, body = request.method, await request.body()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(method, url, content=body, headers=headers)
        if resp.status_code == 401:
            token = SessionManager.refresh()
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, url, content=body, headers=headers)
        return resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.content

# --- OLLAMA PROXY (Throttled) ---
@app.post("/ollama/v1/chat")
async def proxy_ollama(request: Request):
    """
    SRE: The MacBook Shield.
    Serializes all heavy LLM requests to prevent resource starvation.
    """
    body = await request.json()
    logger.info(f"Sidecar: Queuing LLM request for model {body.get('model')}...")
    
    async with ollama_semaphore:
        logger.info(f"Sidecar: Processing LLM request (Lock Acquired)...")
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post("http://localhost:11434/api/chat", json=body)
            return resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
