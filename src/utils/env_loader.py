import os
from pathlib import Path
from dotenv import load_dotenv

class EnvLoader:
    """
    Standardized environment loader for the BestFam ecosystem.
    Prioritizes:
    1. OS Environment variables.
    2. Local .env file.
    3. Shared Homelab secrets (if available).
    """
    @staticmethod
    def load(project_root: str):
        # 1. Load local .env
        local_env = Path(project_root) / ".env"
        if local_env.exists():
            load_dotenv(local_env)
            print(f"✅ Loaded local environment from {local_env}")

        # 2. Load shared secrets (Decrypted SOPS files)
        shared_env = Path("/Users/grantbest/Documents/Active/Homelab/shared-services/.env")
        if shared_env.exists():
            load_dotenv(shared_env)
            print(f"🔐 Loaded shared secrets from Homelab")

    @staticmethod
    def get(key: str, default: str = None) -> str:
        val = os.getenv(key, default)
        if not val:
            # SRE Alert: Missing critical secret
            print(f"⚠️  WARNING: Critical secret '{key}' is missing!")
        return val
