import os
import json
import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Activities
from src.workers.mayor_workflow import (
    triage_task_queue,
    move_task_activity
)
from src.workers.polecat_activities import polecat_developer_activity

@workflow.defn(name="ImplementationWorkflow")
class ImplementationWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=3)
        fast_retry = RetryPolicy(maximum_attempts=1)
        
        # 1. Triage
        target_queue = await workflow.execute_activity(
            triage_task_queue, bead_id,
            start_to_close_timeout=timedelta(seconds=60), retry_policy=fast_retry)

        # 2. Implement
        dev_result = await workflow.execute_activity(
            polecat_developer_activity, bead_id,
            start_to_close_timeout=timedelta(minutes=30),
            task_queue=target_queue, retry_policy=fast_retry)

        if isinstance(dev_result, str) and ("ERROR" in dev_result.upper() or "EXCEPTION" in dev_result.upper()):
            raise Exception(f"Implementation Failed: {dev_result}")

        # 3. Move to Validation
        await workflow.execute_activity(
            move_task_activity, 
            args=[str(bead_id), "Validation"],
            start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

        return f"Implementation complete: {dev_result}"
