import os
import subprocess
import json
import logging
import re
from typing import List, Optional, Dict, Any
from src.utils.model_router import ModelRouter

class DeveloperAgent:
    """
    Developer Agent (Gastown Polecat Brain).
    Implements a multi-stage execution strategy for maximum resilience.
    Stage 1: Containerized Aider (Robust, isolated)
    Stage 2: Native File-Writer (Lightweight LLM call + File I/O)
    """
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.router = ModelRouter()
        self.logger = logging.getLogger("DeveloperAgent")

    async def implement_feature(self, task_title: str, instruction: str, files: List[str]) -> str:
        """
        Primary entry point for feature implementation with self-verification.
        """
        print(f"👨‍💻 DeveloperAgent: Starting task '{task_title}'")
        
        implementation_result = ""
        
        # --- STAGE 1: CONTAINERIZED AIDER ---
        try:
            print("📦 Stage 1: Attempting implementation via Containerized Aider...")
            result = await self._implement_via_docker_aider(task_title, instruction, files)
            
            error_keywords = ["BadRequestError", "AnthropicException", "credit balance is too low", "Invalid API Key"]
            has_error = any(keyword in result for keyword in error_keywords)
            
            if "SUCCESS" in result and not has_error:
                implementation_result = result
            else:
                print(f"⚠️ Stage 1 Failed (or encountered API error). Result: {result[:200]}...")
        except Exception as e:
            print(f"⚠️ Stage 1 Error: {e}")

        # --- STAGE 2: NATIVE FILE-WRITER ---
        if not implementation_result:
            try:
                print("🐍 Stage 2: Falling back to Native File-Writer (Using Resilient ModelRouter)...")
                implementation_result = await self._implement_via_native_llm(task_title, instruction)
            except Exception as e:
                return f"❌ Stage 2 Exception: {str(e)}"

        if "SUCCESS" not in implementation_result:
            return implementation_result

        # --- VERIFICATION GATE ---
        print("🧪 Implementation applied. Running self-verification...")
        verification_result = await self._verify_implementation()
        
        # --- GASTOWN DEPOSIT: Commit changes to Git ---
        if "SUCCESS" in verification_result:
            print("💾 Verification passed. Committing changes to branch...")
            try:
                subprocess.run(["git", "-C", self.workspace_root, "add", "."], check=True)
                subprocess.run(["git", "-C", self.workspace_root, "commit", "-m", f"Polecat: {task_title}"], check=True)
                print("✅ Changes committed successfully.")
            except Exception as e:
                print(f"⚠️ Git Commit failed: {e}")
        
        return f"{implementation_result}\n\nVERIFICATION: {verification_result}"

    async def _verify_implementation(self) -> str:
        """
        Runs the project test suite in the isolated worktree.
        """
        pytest_bin = "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/pytest"
        
        self.logger.info(f"🧪 Running self-verification in {self.workspace_root}")
        
        try:
            process = subprocess.run(
                [pytest_bin, "."],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if process.returncode == 0:
                return "✅ SUCCESS: All tests passed in the isolated worktree."
            else:
                return f"❌ FAILED: Tests failed after implementation.\n{process.stdout}"
        except Exception as e:
            return f"⚠️ ERROR during verification: {str(e)}"

    async def _implement_via_docker_aider(self, task_title: str, instruction: str, files: List[str]) -> str:
        """
        Executes Aider inside a Docker container to ensure environment isolation.
        """
        # Ensure workspace_root is absolute
        abs_workspace = os.path.abspath(self.workspace_root)
        
        # Build Docker command
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_workspace}:/app",
            "-w", "/app",
        ]

        # Pass keys only if they exist
        if os.getenv('ANTHROPIC_API_KEY'):
            cmd.extend(["-e", f"ANTHROPIC_API_KEY={os.getenv('ANTHROPIC_API_KEY')}"])
        if os.getenv('OPENAI_API_KEY'):
            cmd.extend(["-e", f"OPENAI_API_KEY={os.getenv('OPENAI_API_KEY')}"])
        if os.getenv('GEMINI_API_KEY'):
            cmd.extend(["-e", f"GEMINI_API_KEY={os.getenv('GEMINI_API_KEY')}"])

        cmd.extend([
            "paulgauthier/aider-full",
            "--yes",
            "--no-git", # Critical: We are already in a worktree managed by the Polecat
            "--message", f"TASK: {task_title}\nINSTRUCTION: {instruction}"
        ])
        
        if files:
            cmd.extend(files)

        self.logger.info(f"📦 Executing Docker Aider in {abs_workspace}")
        
        try:
            # Using run() instead of Popen for synchronous waiting with timeout
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600 # 10 minute timeout for the implementation
            )

            if process.returncode == 0:
                return f"SUCCESS: (Docker Aider)\n{process.stdout}"
            else:
                return f"ERROR: (Docker Aider) code {process.returncode}\n{process.stderr}"
        except subprocess.TimeoutExpired:
            return "ERROR: (Docker Aider) implementation timed out after 10 minutes."
        except Exception as e:
            return f"ERROR: (Docker Aider) Exception: {str(e)}"

    async def _implement_via_native_llm(self, task_title: str, instruction: str) -> str:
        """
        Calls the LLM directly, asks for specific file changes, and applies them.
        """
        # SRE: Provide the agent with the current file list to avoid placeholder paths
        file_list = []
        for root, dirs, files in os.walk(self.workspace_root):
            for name in files:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, self.workspace_root)
                if not any(x in rel_path for x in ['.git', '__pycache__', '.beads', '.venv']):
                    file_list.append(rel_path)
        
        system_prompt = f"""You are a senior software engineer. 
        Analyze the task and provide the code changes.
        
        CURRENT FILES IN WORKSPACE:
        {', '.join(file_list[:100])}

        INSTRUCTIONS:
        1. Use ACTUAL file paths from the list above if you are modifying existing files.
        2. If creating new files, use a logical path structure (e.g., 'services/new_service.py').
        3. Respond ONLY with a JSON list of objects, one for each file change:
        [
          {{"path": "path/to/file.py", "content": "Full file content here..."}}
        ]
        Respond ONLY with the JSON block."""

        prompt = f"TASK: {task_title}\nWORKSPACE ROOT: {self.workspace_root}\nINSTRUCTION: {instruction}"
        
        response = await self.router.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_model="complex",
            json_mode=True
        )

        # Parse the JSON response
        # The ModelRouter with json_mode=True returns a dict/list directly
        changes = response
        
        # Flexibility: Handle various JSON structures LLMs might use
        if isinstance(changes, dict):
            if "changes" in changes:
                changes = changes["changes"]
            elif "path" in changes and "content" in changes:
                # Case where LLM returns a single dict instead of a list
                changes = [changes]
            elif all(isinstance(v, str) for v in changes.values()) and any("/" in k or "." in k for k in changes.keys()):
                # Case where LLM returns {"file.py": "content"}
                changes = [{"path": k, "content": v} for k, v in changes.items()]
        
        if not isinstance(changes, list):
            self.logger.error(f"Native LLM invalid format. Response: {response}")
            return f"ERROR: Native LLM returned invalid format: {type(changes)}. See logs for details."

        applied_files = []
        for change in changes:
            if not isinstance(change, dict) or "path" not in change or "content" not in change:
                continue
                
            file_path = os.path.join(self.workspace_root, change.get("path"))
            content = change.get("content")
            
            # Ensure parent directories exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "w") as f:
                f.write(content)
            
            applied_files.append(change.get("path"))

        return f"SUCCESS: (Native LLM) Applied changes to: {', '.join(applied_files)}"
