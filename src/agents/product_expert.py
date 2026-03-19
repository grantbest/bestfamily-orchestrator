import os
import json
from typing import Dict, Any, List, Optional
from src.utils.model_router import ModelRouter

class ProductExpertAgent:
    """
    Agent specializing in Product Management and System Analysis.
    Uses ModelRouter for resilient cross-provider support.
    """
    def __init__(self):
        self.router = ModelRouter()
        self.system_prompt = (
            "You are a Senior AI Product Expert. Your goal is to maximize agentic automation "
            "in the SDLC while keeping humans in the outer loop via Vikunja. "
            "You focus on MVP features, IaC, and pipeline-driven solutions."
        )

    async def define_scope(self, epic_title: str, user_vision: str) -> Dict[str, Any]:
        """
        Analyzes a vision and provides a structured set of solution scope requirements.
        """
        prompt = f"""
        EPIC VISION: {epic_title}
        USER VISION: {user_vision}
        
        INSTRUCTIONS:
        Assess the problem and provide a structured SOLUTION SCOPE.
        Use HIGHLY READABLE Markdown:
        - Use bullet points for requirements.
        - Use bold text for emphasis.
        - Ensure clear paragraph breaks.
        
        Focus on Phase-1 MVP features.
        Align to three work streams:
        1. NEW CAPABILITIES (Creating new features)
        2. ENHANCEMENTS (Improving existing features)
        3. SUPPORT (Bugs, Defects, Security)

        The scope MUST leverage:
        - Infrastructure as Code (IaC)
        - CI/CD Pipeline integration
        - Agentic 'Meta-Testing' Evidence
        - Automated SRE fallback

        OUTPUT FORMAT (JSON):
        {{
          "product_analysis": "Detailed summary with clear paragraphs and bulleted highlights",
          "phase_1_mvp_requirements": [
            {{ "id": "REQ-1", "stream": "NEW|ENHANCE|SUPPORT", "requirement": "title", "acceptance_criteria": "Clear bulleted ACs" }}
          ],
          "automation_strategy": "Bulleted list of how agents replace human steps",
          "iac_pipeline_impact": "Detailed impact with technical specifics",
          "sre_fallback_scenarios": ["Bulleted scenario 1", "Bulleted scenario 2"]
        }}
        """

        try:
            return await self.router.chat(
                prompt=prompt,
                system_prompt=self.system_prompt,
                preferred_model="auto",
                json_mode=True
            )
        except Exception as e:
            print(f"ProductExpert: AI analysis failed: {e}")
            # Manual Fallback for MVP Stability
            return {
                "product_analysis": "Automating the SDLC to move humans to the outer loop.",
                "phase_1_mvp_requirements": [
                    {
                        "id": "REQ-NEW-01",
                        "stream": "NEW",
                        "requirement": "Agent-driven Scaffolding",
                        "acceptance_criteria": "Agent creates directory structure and boilerplate from Vikunja trigger."
                    }
                ],
                "automation_strategy": "Replace human manual CLI tasks with Temporal Activity execution.",
                "iac_pipeline_impact": "Terraform for DNS/Cloudflare, Docker for isolated worker pools.",
                "sre_fallback_scenarios": ["Temporal Activity Failure"]
            }
