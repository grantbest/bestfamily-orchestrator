import os
import json
from typing import Dict, Any, Optional
from src.utils.model_router import ModelRouter

class SREAgent:
    """
    SRE Agent for investigating failures, analyzing logs, and proposing/applying infra fixes.
    Uses ModelRouter for resilient cross-provider support.
    """
    def __init__(self):
        self.router = ModelRouter()

    async def diagnose(self, title: str, description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Diagnoses an issue and returns a proposed resolution or action.
        """
        prompt = f"""
        You are a Senior Site Reliability Engineer (SRE).
        ISSUE: {title}
        DESCRIPTION: {description}
        CONTEXT: {json.dumps(context or {})}
        
        INSTRUCTIONS:
        1. Analyze the issue for root causes.
        2. Propose a specific technical fix (e.g., shell commands, config changes).
        3. Provide a summary of your reasoning.
        
        OUTPUT FORMAT (JSON):
        {{
          "diagnosis": "Root cause analysis",
          "proposed_fix": "The technical fix description",
          "action_commands": ["list", "of", "commands", "to", "run"],
          "confidence": 0.0 to 1.0
        }}
        """

        try:
            return await self.router.chat(
                prompt=prompt,
                system_prompt="You are a Senior SRE.",
                preferred_model="auto",
                json_mode=True
            )
        except Exception as e:
            # SRE should be able to operate even with simple rules if AI fails
            return {
                "diagnosis": f"AI Diagnosis Unavailable: {e}",
                "proposed_fix": "Perform manual investigation of logs and infrastructure.",
                "action_commands": [],
                "confidence": 0.0
            }

    def apply_pipeline_fix(self, file_path: str) -> str:
        """
        Legacy rule-based fix for pipeline caching (migrated from old SRE script).
        """
        if not os.path.exists(file_path):
            return f"Error: {file_path} not found."

        with open(file_path, "r") as f:
            content = f.read()

        updated = False
        if "docker build" in content and "--no-cache" not in content:
            content = content.replace("docker build", "docker build --no-cache")
            updated = True
        
        if "compose up -d" in content and "--force-recreate" not in content:
            content = content.replace("compose up -d", "compose up -d --force-recreate")
            updated = True
            
        if updated:
            with open(file_path, "w") as f:
                f.write(content)
            return "SUCCESS: Applied pipeline safety flags (--no-cache, --force-recreate)."
        
        return "INFO: Pipeline already contains required SRE safety flags."
