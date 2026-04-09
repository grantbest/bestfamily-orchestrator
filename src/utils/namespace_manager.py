import os
from typing import List

class NamespaceManager:
    """
    SRE: Centralized mapping of Gastown task types to Temporal Namespaces.
    Supports robust routing via Vikunja Labels (Attributes).
    """
    
    @staticmethod
    def get_namespace_for_task(title: str = "", description: str = "", labels: List[str] = None) -> str:
        # 1. PRIORITY: Attribute-based routing via Labels
        if labels:
            for label in labels:
                l = label.lower()
                if "betting" in l: return "betting-app"
                if "homelab" in l or "infra" in l: return "homelab"
                if "core" in l or "orchestrator" in l: return "default"

        # 2. FALLBACK: Pattern-based routing via Title/Description
        t = title.lower()
        d = description.lower()
        
        if any(kw in t or kw in d for kw in ["homelab", "infrastructure", "refinery", "pipeline", "dns", "[infra]", "infra:"]):
            return "homelab"
            
        if any(kw in t or kw in d for kw in ["betting", "api", "ui", "frontend", "backend", "auth", "[app]", "app:"]):
            return "betting-app"
            
        return "default"

    @staticmethod
    def get_queue_for_namespace(namespace: str) -> str:
        mapping = {
            "default": "modular-orchestrator-queue",
            "betting-app": "betting-app-queue",
            "homelab": "homelab-queue"
        }
        return mapping.get(namespace, "modular-orchestrator-queue")
