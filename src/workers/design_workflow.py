import os
import json
import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
from src.workers.mayor_workflow import (
    ba_design_activity,
    architect_design_activity,
    game_designer_activity,
    domain_experts_activity,
    quarterback_synthesis_activity
)

@workflow.defn
class DesignWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=3)
        
        # 1. BA Scope
        scope = await workflow.execute_activity(
            ba_design_activity, bead_id,
            start_to_close_timeout=timedelta(minutes=15), retry_policy=retry)

        # 2. Architect Design
        design = await workflow.execute_activity(
            architect_design_activity, scope,
            start_to_close_timeout=timedelta(minutes=15), retry_policy=retry)

        # 3. Game Designer Review
        game_questions = await workflow.execute_activity(
            game_designer_activity,
            args=[scope.get("title", ""), scope.get("product_analysis", "")],
            start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)

        # 4. Domain Expert Review (SRE/Security)
        infra_questions = await workflow.execute_activity(
            domain_experts_activity,
            args=[design, scope.get("title", "")],
            start_to_close_timeout=timedelta(minutes=5), retry_policy=retry)

        # 5. Synthesis
        return await workflow.execute_activity(
            quarterback_synthesis_activity,
            args=[bead_id, scope, design, infra_questions, game_questions],
            start_to_close_timeout=timedelta(minutes=2))
