import os
import json
from typing import Dict, Any, List, Optional
from src.utils.model_router import ModelRouter

class GameDesignerAgent:
    """
    Agent specializing in Educational Game Design and Kid-Friendly UX.
    Focuses on engagement, math pedagogy, and fun mechanics.
    """
    def __init__(self):
        self.router = ModelRouter()
        self.system_prompt = (
            "You are a Senior Educational Game Designer. Your goal is to make learning fun, "
            "interactive, and highly engaging for kids. You focus on 'Game Loops', 'Progression', "
            "and 'Pedagogy' (how they learn math while playing)."
        )

    async def review_design(self, title: str, description: str) -> List[str]:
        """
        Reviews a game design and provides critical questions from a designer's perspective.
        """
        prompt = f"""
        GAME TITLE: {title}
        DESCRIPTION: {description}
        
        INSTRUCTIONS:
        Review this educational math game design. 
        Provide exactly 3 critical, conversational, and fun questions for the user (or their kid!)
        that help refine the GAMEPLAY and FUN factor.
        
        Focus on:
        1. The Alien bonding/feeding mechanic.
        2. The Math-to-Ability mapping (how math helps them win).
        3. The Gacha/Collectible excitement.

        FORMAT: Respond ONLY with a JSON list of strings.
        """

        try:
            return await self.router.chat(
                prompt=prompt,
                system_prompt=self.system_prompt,
                preferred_model="auto",
                json_mode=True
            )
        except Exception as e:
            print(f"GameDesigner: Failed to generate questions: {e}")
            return ["What makes the aliens happy when you feed them?", "How do aliens help you solve hard math?"]
