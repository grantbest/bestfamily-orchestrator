import asyncio
import os
import json
import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Activities
from src.workers.mayor_workflow import (
    breakdown_activity,
    mark_breakdown_started_activity,
    move_task_activity
)

logger = logging.getLogger(__name__)

@workflow.defn(name="BreakdownWorkflow")
class BreakdownWorkflow:
    @workflow.run
    async def run(self, bead_id: str) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=3)
        
        # 1. Mark Breakdown Started (Anti-loop)
        await workflow.execute_activity(
            mark_breakdown_started_activity, bead_id,
            start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

        # 2. Perform Breakdown
        breakdown_result = await workflow.execute_activity(
            breakdown_activity, bead_id,
            start_to_close_timeout=timedelta(minutes=10), retry_policy=retry)

        try:
            story_ids = json.loads(breakdown_result)
        except Exception:
            return f"Breakdown complete (no story IDs): {breakdown_result}"

        # 3. Fan-out: Start Child Workflows
        from src.utils.namespace_manager import NamespaceManager
        story_handles = []
        for story_id in story_ids:
            # SRE: Determine the correct namespace for this story
            # In a breakdown, the child story might belong to a different namespace
            # We fetch the story title to triage it correctly
            story_bead = await workflow.execute_activity(
                get_task_title_activity, story_id,
                start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)
            
            target_ns = NamespaceManager.get_namespace_for_task(title=story_bead)
            target_queue = NamespaceManager.get_queue_for_namespace(target_ns)
            
            logger.info(f"Breakdown[{bead_id}]: Starting ImplementationWorkflow for story {story_id} in namespace {target_ns}")
            
            # Each story gets an ImplementationWorkflow
            handle = await workflow.start_child_workflow(
                "ImplementationWorkflow",
                str(story_id),
                id=f"implementation-task-{story_id}-doing",
                namespace=target_ns, # TARGET THE DEDICATED NAMESPACE
                task_queue=target_queue
            )
            story_handles.append(handle)
            
            # 4. Move story to 'Doing' in Vikunja
            logger.info(f"Breakdown[{bead_id}]: Moving story {story_id} to Doing")
            await workflow.execute_activity(
                move_task_activity, 
                args=[str(story_id), "Doing"],
                start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

        # 5. Await all children (Safe since we use UnsandboxedWorkflowRunner)
        await asyncio.gather(*story_handles)
        
        # 6. Move Epic to Validation
        await workflow.execute_activity(
            move_task_activity, 
            args=[str(bead_id), "Validation"],
            start_to_close_timeout=timedelta(seconds=30), retry_policy=retry)

        return f"Breakdown complete. {len(story_ids)} stories processed."
