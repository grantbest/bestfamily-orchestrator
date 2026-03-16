import os
import subprocess
import json
from typing import List, Optional

class DeveloperAgent:
    """
    Developer Agent that uses Aider to write code and manage git branches.
    Implements a Hybrid Strategy for cost-efficiency.
    """
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def select_model(self, task_description: str) -> str:
        """
        HYBRID STRATEGY: Selects the model based on task complexity.
        """
        complex_keywords = ["refactor", "architecture", "security", "optimization", "complex"]
        is_complex = any(keyword in task_description.lower() for keyword in complex_keywords)

        if is_complex and self.anthropic_key:
            return "claude-3-5-sonnet-20241022"
        elif self.gemini_key:
            return "gemini/gemini-1.5-flash"
        else:
            return "ollama/llama3"

    async def implement_feature(self, task_title: str, instruction: str, files: List[str]) -> str:
        """
        Executes Aider CLI to implement a feature.
        """
        model = self.select_model(instruction)
        print(f"👨‍💻 DeveloperAgent: Starting task '{task_title}' using {model}")

        # Ensure we are in the correct directory
        os.chdir(self.workspace_root)

        # Build Aider command
        # --yes: auto-accept changes
        # --message: the instruction
        # --model: the chosen hybrid model
        cmd = [
            "aider",
            "--yes",
            "--message", f"TASK: {task_title}\nINSTRUCTION: {instruction}",
            "--model", model
        ]
        
        # Add specific files if provided to minimize context cost
        if files:
            cmd.extend(files)

        try:
            # Set up environment for Aider (pass keys)
            env = os.environ.copy()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                return f"SUCCESS: Feature '{task_title}' implemented via Aider ({model}).\n{stdout}"
            else:
                return f"ERROR: Aider failed with code {process.returncode}.\n{stderr}"

        except Exception as e:
            return f"EXCEPTION: Failed to run Aider: {str(e)}"
