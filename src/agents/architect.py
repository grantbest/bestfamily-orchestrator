import os
import json
from typing import Dict, Any, Optional
from src.utils.model_router import ModelRouter

class ArchitectAgent:
    """
    Architect Agent for designing system architecture and refining beads.
    Uses ModelRouter for resilient cross-provider support.
    """
    def __init__(self):
        self.router = ModelRouter()
        self.system_prompt = (
            "You are a Senior System Architect. You must respond ONLY with a valid JSON object. "
            "Maintain a SINGLE SOURCE OF TRUTH design document."
        )

    async def analyze(self, title: str, current_description: str, history: str) -> Dict[str, Any]:
        """
        Processes design requests and returns a structured JSON response.
        """
        prompt = f"""
        TASK: {title}
        CONTEXT: {current_description}
        FEEDBACK: {history}
        
        INSTRUCTIONS:
        1. Rewrite the TASK DESCRIPTION into a professional Markdown design doc.
        2. Use headers: # [Title], ## Business Requirements, ## Recommended Solution Design, ## Acceptance Criteria.
        3. Use bullet points for all lists and sub-tasks.
        4. Use bold text for key technical components.
        5. Ensure double newlines between sections for readability.
        6. End with '[AGENT_SIGNATURE]'.
        
        REQUIRED JSON KEYS:
        - "updated_description": "The full structured markdown string"
        - "follow_up": "Next steps"
        - "needs_more_info": false
        """

        try:
            return await self.router.chat(
                prompt=prompt,
                system_prompt=self.system_prompt,
                preferred_model="complex",
                json_mode=True
            )
        except Exception as e:
            raise RuntimeError(f"ArchitectAgent: Failed to generate design: {e}")
