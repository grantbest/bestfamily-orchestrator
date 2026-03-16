import asyncio
import unittest
from unittest.mock import patch, MagicMock
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from src.workers.pipeline_workflow import (
    MasterPipelineWorkflow, 
    discovery_activity,
    check_changes_activity,
    build_activity, 
    test_activity, 
    secure_activity, 
    deploy_activity,
    create_sre_bug_activity
)

class TestConditionalDeployment(unittest.IsolatedAsyncioTestCase):
    async def test_skip_unchanged_service(self):
        async with await WorkflowEnvironment.start_local() as env:
            # Mock Discovery and Hash
            with patch('src.agents.product_expert.ProductExpertAgent.define_scope') as mock_scope:
                mock_scope.return_value = {"product_analysis": "Test"}
                
                # We'll use a fixed hash to simulate 'no change'
                fixed_hash = "same-hash-123"
                
                with patch('src.utils.change_detector.ChangeDetector.get_directory_hash') as mock_hash:
                    mock_hash.return_value = fixed_hash
                    
                    async with Worker(
                        env.client,
                        task_queue="test-conditional-queue",
                        workflows=[MasterPipelineWorkflow],
                        activities=[
                            discovery_activity,
                            check_changes_activity,
                            build_activity, 
                            test_activity, 
                            secure_activity, 
                            deploy_activity,
                            create_sre_bug_activity
                        ],
                    ):
                        # Define two services: one matches the hash (skip), one doesn't (deploy)
                        services = [
                            {"name": "unchanged-service", "path": "/tmp/app1", "last_hash": fixed_hash},
                            {"name": "changed-service", "path": "/tmp/app2", "last_hash": "old-hash"}
                        ]

                        result = await env.client.execute_workflow(
                            MasterPipelineWorkflow.run,
                            args=["bead-61", "Test", "Vision", services],
                            id="test-conditional-run",
                            task_queue="test-conditional-queue",
                        )
                        
                        self.assertIn("unchanged-service: Skipped", result)
                        self.assertIn("changed-service: Deployed", result)
                        print(f"\n✅ Meta-Testing Evidence: {result}")

if __name__ == "__main__":
    unittest.main()
