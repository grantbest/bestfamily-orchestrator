import os
import json
from typing import Dict, Any, Optional
from google import genai

class SREAgent:
    """
    SRE Agent for investigating failures, analyzing logs, and proposing/applying infra fixes.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

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
                print(f"SREAgent: Gemini failed: {e}")

        # 2. Fallback to Ollama
        try:
            import ollama
            o_client = ollama.Client(host=self.ollama_host)
            response = o_client.chat(
                model="llama3:latest",
                messages=[{'role': 'user', 'content': prompt}],
                format='json'
            )
            return json.loads(response['message']['content'])
        except Exception as e:
            # SRE should be able to operate even with simple rules if AI fails
            return {
                "diagnosis": "AI Diagnosis Unavailable",
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
