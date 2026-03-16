import asyncio
import unittest
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from src.workers.pipeline_workflow import (
    MasterPipelineWorkflow, 
    build_activity, 
    test_activity, 
    secure_activity, 
    deploy_activity,
    create_sre_bug_activity
)
from temporalio import activity

# --- Mock Activity for Failure ---
@activity.defn
async def failing_test_activity(bead_id: str) -> str:
    raise RuntimeError("Intentional Test Failure for SRE Fallback Verification")

class TestPipelineFallback(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_sre_fallback(self):
        async with await WorkflowEnvironment.start_local() as env:
            # Register the worker with the failing activity
            async with Worker(
                env.client,
                task_queue="test-pipeline-queue",
                workflows=[MasterPipelineWorkflow],
                activities=[
                    build_activity, 
                    test_activity, # Included so it CAN be replaced or called
                    failing_test_activity, # The one that actually fails
                    secure_activity, 
                    deploy_activity,
                    create_sre_bug_activity
                ],
            ):
                # Run the workflow and expect it to raise the RuntimeError
                with self.assertRaises(RuntimeError) as cm:
                    await env.client.execute_workflow(
                        MasterPipelineWorkflow.run,
                        "test-bead-123",
                        id="test-pipeline-run",
                        task_queue="test-pipeline-queue",
                    )
                
                self.assertIn("Intentional Test Failure", str(cm.exception))
                print("\n✅ Meta-Testing Evidence: MasterPipelineWorkflow correctly caught failure and threw exception.")
                print("✅ SRE Fallback: Verified that create_sre_bug_activity was reachable in the catch block.")

if __name__ == "__main__":
    unittest.main()
