import os
import json
from typing import Dict, Any, Optional
from google import genai

class ArchitectAgent:
    """
    Refined Architect Agent for designing system architecture and refining beads.
    Handles Gemini 2.0 with Ollama (Llama3) fallback.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        # Use host.docker.internal inside container
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
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
        3. End with '[AGENT_SIGNATURE]'.
        
        REQUIRED JSON KEYS:
        - "updated_description": "The full markdown string"
        - "follow_up": "Next steps"
        - "needs_more_info": false
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
                print(f"ArchitectAgent: Gemini failed: {e}")

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
            raise RuntimeError(f"ArchitectAgent: Both Gemini and Ollama failed: {e}")
