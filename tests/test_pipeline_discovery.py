import asyncio
import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from src.workers.pipeline_workflow import (
    MasterPipelineWorkflow, 
    discovery_activity,
    build_activity, 
    test_activity, 
    secure_activity, 
    deploy_activity,
    create_sre_bug_activity
)

class TestPipelineDiscovery(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_with_discovery(self):
        async with await WorkflowEnvironment.start_local() as env:
            # Mock the define_scope call to avoid real AI calls during test
            with patch('src.agents.product_expert.ProductExpertAgent.define_scope') as mock_scope:
                mock_scope.return_value = {"product_analysis": "Test Scope", "phase_1_mvp_requirements": []}
                
                async with Worker(
                    env.client,
                    task_queue="test-discovery-queue",
                    workflows=[MasterPipelineWorkflow],
                    activities=[
                        discovery_activity,
                        build_activity, 
                        test_activity, 
                        secure_activity, 
                        deploy_activity,
                        create_sre_bug_activity
                    ],
                ):
                    result = await env.client.execute_workflow(
                        MasterPipelineWorkflow.run,
                        args=["bead-54", "Test Epic", "Test Vision"],
                        id="test-discovery-run",
                        task_queue="test-discovery-queue",
                    )
                    
                    self.assertEqual(result, "Pipeline Completed Successfully")
                    mock_scope.assert_called_once_with("Test Epic", "Test Vision")
                    print("\n✅ Meta-Testing Evidence: MasterPipelineWorkflow successfully integrated Discovery phase.")

if __name__ == "__main__":
    unittest.main()
