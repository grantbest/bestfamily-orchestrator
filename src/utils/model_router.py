import asyncio
import os
import json
import logging
from typing import Dict, Any, List, Optional

class ModelRouter:
    """
    Central utility to route LLM requests across multiple providers.
    Supports Gemini, OpenAI, Claude, and Ollama.
    """
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    async def chat(self,
                   prompt: str,
                   system_prompt: str = "You are a helpful assistant.",
                   preferred_model: str = "auto",
                   json_mode: bool = True) -> Dict[str, Any]:
        """
        Executes a chat request with automatic fallback logic.
        GASTOWN MANDATE: Prioritize local gemma4 for MacBook execution.
        """
        # PRIORITY 1: Local Gemma 4 (MacBook Power)
        model_priority = [("ollama", "gemma4:latest")]

        # Fallbacks (Optional)
        if preferred_model == "complex":
            if self.openai_key: model_priority.append(("openai", "gpt-4o"))
            if self.gemini_key: model_priority.append(("gemini", "gemini-2.0-flash"))
        elif preferred_model == "fast":
            if self.openai_key: model_priority.append(("openai", "gpt-4o-mini"))
            if self.gemini_key: model_priority.append(("gemini", "gemini-2.0-flash"))
        elif preferred_model == "claude":
            if self.anthropic_key: model_priority.append(("anthropic", "claude-3-5-sonnet-20241022"))
        elif preferred_model == "ollama":
            pass # Already at top
        else:
            if self.openai_key: model_priority.append(("openai", "gpt-4o"))
            if self.gemini_key: model_priority.append(("gemini", "gemini-2.0-flash"))

        for provider, model in model_priority:
            max_retries = 3
            backoff_base = 2
            
            for attempt in range(max_retries):
                try:
                    logging.info(f"ModelRouter: Trying {provider}/{model} (Attempt {attempt+1}/{max_retries})")
                    if provider == "gemini":
                        return await self._call_gemini(prompt, system_prompt, model, json_mode)
                    elif provider == "openai":
                        return await self._call_openai_compatible(prompt, system_prompt, model, "https://api.openai.com/v1", self.openai_key, json_mode)
                    elif provider == "anthropic":
                        return await self._call_anthropic(prompt, system_prompt, model, json_mode)
                    elif provider == "ollama":
                        return await self._call_ollama(prompt, system_prompt, model, json_mode)
                except Exception as e:
                    error_str = str(e).lower()
                    if "404" in error_str or "not found" in error_str:
                        logging.warning(f"ModelRouter: {provider}/{model} not found: {e}. Moving to next provider.")
                        break
                    
                    if attempt < max_retries - 1:
                        sleep_time = backoff_base ** attempt
                        logging.warning(f"ModelRouter: {provider}/{model} failed with '{e}'. Retrying in {sleep_time}s...")
                        await asyncio.sleep(sleep_time)
                    else:
                        logging.warning(f"ModelRouter: {provider}/{model} failed after {max_retries} attempts: {e}")

        raise RuntimeError("ModelRouter: All models and fallbacks failed after retries.")

    async def _call_gemini(self, prompt, system, model, json_mode):
        try:
            from google import genai
        except ImportError:
            raise ImportError("Google GenAI SDK not installed.")

        client = genai.Client(api_key=self.gemini_key)
        config = {'response_mime_type': 'application/json'} if json_mode else None
        full_prompt = f"{system}\n\n{prompt}"

        def _sync():
            response = client.models.generate_content(model=model, contents=full_prompt, config=config)
            return json.loads(response.text) if json_mode else response.text

        return await asyncio.to_thread(_sync)

    async def _call_openai_compatible(self, prompt, system, model, base_url, api_key, json_mode):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI SDK not installed.")

        client = OpenAI(api_key=api_key, base_url=base_url)
        response_format = {"type": "json_object"} if json_mode else None

        def _sync():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                response_format=response_format
            )
            content = response.choices[0].message.content
            return json.loads(content) if json_mode else content

        return await asyncio.to_thread(_sync)

    async def _call_anthropic(self, prompt, system, model, json_mode):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Anthropic SDK not installed.")

        client = anthropic.Anthropic(api_key=self.anthropic_key)

        def _sync():
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            return json.loads(content) if json_mode else content

        return await asyncio.to_thread(_sync)

    async def _call_ollama(self, prompt, system, model, json_mode):
        try:
            import ollama
        except ImportError:
            raise ImportError("Ollama SDK not installed.")

        o_client = ollama.Client(host=self.ollama_host)

        def _sync():
            response = o_client.chat(
                model=model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt}
                ],
                format='json' if json_mode else None
            )
            content = response['message']['content']
            return json.loads(content) if json_mode else content

        return await asyncio.to_thread(_sync)
