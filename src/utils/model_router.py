import asyncio
import os
import json
import logging
from typing import Dict, Any, List, Optional

class ModelRouter:
    """
    SRE: Hardware-Aware Model Routing with Proxy Support.
    Tiers models and routes local requests through the Sidecar for queuing.
    """
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        # SRE: Use the Sidecar Proxy for all local LLM calls
        self.ollama_proxy = "http://localhost:8001/ollama/v1/chat"

    async def chat(self,
                   prompt: str,
                   system_prompt: str = "You are a helpful assistant.",
                   preferred_model: str = "auto",
                   json_mode: bool = True) -> Dict[str, Any]:
        
        model_priority = []

        if preferred_model == "fast":
            model_priority.append(("ollama", "gemma:2b")) 
            if self.gemini_key: model_priority.append(("gemini", "gemini-2.0-flash"))
        elif preferred_model == "complex":
            model_priority.append(("ollama", "gemma4:latest"))
            if self.openai_key: model_priority.append(("openai", "gpt-4o"))
        else:
            model_priority.append(("ollama", "gemma3:latest"))
            if self.gemini_key: model_priority.append(("gemini", "gemini-2.0-flash"))

        if ("ollama", "gemma:2b") not in model_priority:
            model_priority.append(("ollama", "gemma:2b"))

        for provider, model in model_priority:
            try:
                logging.info(f"ModelRouter: [{preferred_model}] Trying {provider}/{model}")
                if provider == "gemini":
                    return await self._call_gemini(prompt, system_prompt, model, json_mode)
                elif provider == "openai":
                    return await self._call_openai_compatible(prompt, system_prompt, model, "https://api.openai.com/v1", self.openai_key, json_mode)
                elif provider == "ollama":
                    return await self._call_ollama_proxy(prompt, system_prompt, model, json_mode)
            except Exception as e:
                logging.warning(f"ModelRouter: {provider}/{model} failed: {e}")
                continue

        raise RuntimeError("ModelRouter: All tiers failed.")

    async def _call_gemini(self, prompt, system, model, json_mode):
        from google import genai
        client = genai.Client(api_key=self.gemini_key)
        config = {'response_mime_type': 'application/json'} if json_mode else None
        full_prompt = f"{system}\n\n{prompt}"
        def _sync():
            response = client.models.generate_content(model=model, contents=full_prompt, config=config)
            return json.loads(response.text) if json_mode else response.text
        return await asyncio.to_thread(_sync)

    async def _call_openai_compatible(self, prompt, system, model, base_url, api_key, json_mode):
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response_format = {"type": "json_object"} if json_mode else None
        def _sync():
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                response_format=response_format
            )
            return json.loads(response.choices[0].message.content) if json_mode else response.choices[0].message.content
        return await asyncio.to_thread(_sync)

    async def _call_ollama_proxy(self, prompt, system, model, json_mode):
        import httpx
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': prompt}
            ],
            'format': 'json' if json_mode else None
        }
        # SRE: Long timeout for proxy queuing
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(self.ollama_proxy, json=payload)
            resp.raise_for_status()
            content = resp.json()['message']['content']
            return json.loads(content) if json_mode else content
