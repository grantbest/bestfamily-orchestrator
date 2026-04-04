import os
import subprocess
import shutil
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

    async def implement_feature(self, task_title: str, instruction: str, files: List[str], bead_id: str = "unknown") -> str:
        """
        Primary entry point for feature implementation with self-verification.
        Enhanced Stage 2 (Native File-Writer) with context reading and evidence capture.
        """
        print(f"👨‍💻 DeveloperAgent: Starting task '{task_title}' (Bead: {bead_id})")
        
        implementation_result = ""
        
        # --- NATIVE FILE-WRITER (POLECAT STAGE 2) ---
        try:
            print("🐍 Polecat: Implementing via Native File-Writer (Using Resilient ModelRouter)...")
            implementation_result = await self._implement_via_native_llm(task_title, instruction)
        except Exception as e:
            self.logger.exception("Stage 2 implementation failed")
            return f"❌ Polecat Exception: {str(e)}"

        if "SUCCESS" not in implementation_result:
            return implementation_result

        # --- VERIFICATION GATE ---
        print("🧪 Implementation applied. Running self-verification...")
        verification_result = await self._verify_implementation(bead_id)
        
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

    async def _verify_implementation(self, bead_id: str) -> str:
        """
        Runs the project test suite and captures evidence.
        """
        pytest_bin = shutil.which("pytest") or "/Users/grantbest/Documents/Active/BestFam-Orchestrator/venv/bin/pytest"
        
        self.logger.info(f"🧪 Running self-verification in {self.workspace_root}")
        
        # Ensure evidence directory exists
        evidence_dir = os.path.join(self.workspace_root, "tests", "evidence", bead_id)
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_file = os.path.join(evidence_dir, "pytest_output.txt")
        
        try:
            process = subprocess.run(
                [pytest_bin, "."],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Save evidence
            with open(evidence_file, "w") as f:
                f.write(f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}")
            
            if process.returncode == 0:
                return f"✅ SUCCESS: All tests passed. Evidence saved to {evidence_file}"
            else:
                return f"❌ FAILED: Tests failed after implementation.\n{process.stdout[:1000]}"
        except Exception as e:
            return f"⚠️ ERROR during verification: {str(e)}"

    async def _implement_via_native_llm(self, task_title: str, instruction: str) -> str:
        """
        Enhanced Native LLM implementation:
        1. Identifies relevant files.
        2. Reads their content for context.
        3. Generates and applies changes.
        """
        # 1. Map files in workspace
        file_list = []
        for root, dirs, files in os.walk(self.workspace_root):
            for name in files:
                rel_path = os.path.relpath(os.path.join(root, name), self.workspace_root)
                if not any(x in rel_path for x in ['.git', '__pycache__', '.beads', '.venv', 'node_modules', '.next']):
                    file_list.append(rel_path)
        
        # 2. Heuristic-based context gathering (read top 5 most likely files)
        # In a more advanced version, we'd ask the LLM which files it wants to see.
        context_files = []
        keywords = task_title.lower().split() + instruction.lower().split()
        
        def score_file(path):
            score = 0
            for k in keywords:
                if k in path.lower(): score += 1
            return score

        scored_files = sorted(file_list, key=score_file, reverse=True)[:5]
        
        context_str = ""
        for fpath in scored_files:
            try:
                with open(os.path.join(self.workspace_root, fpath), "r") as f:
                    content = f.read()
                    context_str += f"\n--- FILE: {fpath} ---\n{content}\n"
            except:
                continue

        system_prompt = f"""You are a senior software engineer. 
        Analyze the task and provide the code changes.
        
        CONTEXT FILES CONTENT:
        {context_str}

        WORKSPACE FILE LIST (Subset):
        {', '.join(file_list[:100])}

        INSTRUCTIONS:
        1. Use ACTUAL file paths.
        2. Provide FULL file content for any modified or new files.
        3. Respond ONLY with a JSON list of objects:
        [
          {{"path": "path/to/file.py", "content": "Full file content..."}}
        ]
        Respond ONLY with valid JSON."""

        prompt = f"TASK: {task_title}\nINSTRUCTION: {instruction}"
        
        response = await self.router.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_model="complex",
            json_mode=True
        )

        changes = response
        
        # Flexibility parsing
        if isinstance(changes, dict):
            if "changes" in changes:
                changes = changes["changes"]
            elif "files" in changes:
                changes = changes["files"]
            elif "path" in changes and "content" in changes:
                changes = [changes]
            elif all(isinstance(v, str) for v in changes.values()) and any("." in k for k in changes.keys()):
                # Format: {"file.py": "content"}
                changes = [{"path": k, "content": v} for k, v in changes.items()]

        if not isinstance(changes, list):
            return f"ERROR: Native LLM returned invalid format: {type(changes)}"

        applied_files = []
        for change in changes:
            if not isinstance(change, dict) or "path" not in change or "content" not in change:
                continue
                
            file_path = os.path.join(self.workspace_root, change.get("path"))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "w") as f:
                f.write(change.get("content"))
            
            applied_files.append(change.get("path"))

        return f"SUCCESS: (Native LLM) Applied changes to: {', '.join(applied_files)}"

