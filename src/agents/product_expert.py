import os
import json
from typing import Dict, Any, List, Optional
from google import genai

class ProductExpertAgent:
    """
    Agent specializing in Product Management and System Analysis.
    Translates high-level business goals into structured requirement scopes for autonomous workflows.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        # Use localhost when running directly on Mac host
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
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
        Assess the problem and provide a structured SOLUTION SCOPE for a fully autonomous workflow.
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
          "product_analysis": "Summary of the business problem and AI-automation opportunity",
          "phase_1_mvp_requirements": [
            {{ "id": "REQ-1", "stream": "NEW|ENHANCE|SUPPORT", "requirement": "title", "acceptance_criteria": "..." }}
          ],
          "automation_strategy": "How agents will replace specific human steps in this epic",
          "iac_pipeline_impact": "Impact on Terraform/Docker/Pipeline scripts",
          "sre_fallback_scenarios": ["Scenario 1", "Scenario 2"]
        }}
        """

        # 1. Try Gemini
        if self.api_key:
            try:
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                return json.loads(response.text)
            except Exception as e:
                print(f"ProductExpert: Gemini failed: {e}")

        # 2. Fallback to Ollama
        try:
            import ollama
            o_client = ollama.Client(host=self.ollama_host)
            response = o_client.chat(
                model="llama3:latest",
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': prompt}
                ],
                format='json'
            )
            return json.loads(response['message']['content'])
        except Exception as e:
            print(f"ProductExpert: Ollama failed: {e}")
            # Manual Fallback for MVP Stability
            return {
                "product_analysis": "Automating the SDLC to move humans to the outer loop.",
                "phase_1_mvp_requirements": [
                    {
                        "id": "REQ-NEW-01",
                        "stream": "NEW",
                        "requirement": "Agent-driven Scaffolding",
                        "acceptance_criteria": "Agent creates directory structure and boilerplate from Vikunja trigger."
                    },
                    {
                        "id": "REQ-ENH-02",
                        "stream": "ENHANCE",
                        "requirement": "Pipeline Verification Activities",
                        "acceptance_criteria": "Temporal activities exist for build/test/secure steps."
                    },
                    {
                        "id": "REQ-SUP-03",
                        "stream": "SUPPORT",
                        "requirement": "Automated Bug Bead Creation",
                        "acceptance_criteria": "Workflow catch block creates a Vikunja bead assigned to SRE."
                    }
                ],
                "automation_strategy": "Replace human manual CLI tasks with Temporal Activity execution.",
                "iac_pipeline_impact": "Terraform for DNS/Cloudflare, Docker for isolated worker pools.",
                "sre_fallback_scenarios": ["Temporal Activity Failure", "Ollama/Gemini Rate Limit/Down"]
            }
