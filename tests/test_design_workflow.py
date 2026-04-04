import asyncio
import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from src.workers.mayor_workflow import (
    MayorWorkflow,
    ba_design_activity,
    architect_design_activity,
    domain_experts_activity,
    quarterback_synthesis_activity
)

# --- Mock Activities ---

@activity.defn(name="ba_design_activity")
async def mock_ba_design(bead_id: str) -> dict:
    return {"product_analysis": "Mock Analysis", "automation_strategy": "Mock Strategy"}

@activity.defn(name="architect_design_activity")
async def mock_architect_design(scope: dict) -> dict:
    return {"updated_description": "Mock Architectural Design"}

@activity.defn(name="domain_experts_activity")
async def mock_domain_experts(design: dict, title: str) -> list:
    return ["Mock Question 1?", "Mock Question 2?"]

@activity.defn(name="quarterback_synthesis_activity")
async def mock_quarterback_synthesis(bead_id: str, scope: dict, design: dict, questions: list) -> str:
    return "Synthesis Success"

@activity.defn(name="read_bead_activity")
async def mock_read_bead(bead_id: str) -> dict:
    return {"title": "Test Task", "description": "Test Desc"}

class TestDesignWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_design_phase_orchestration(self):
        """
        Verifies the multi-agent design orchestration sequence.
        """
        # Using UnsandboxedWorkflowRunner to bypass the httpx/urllib restriction during unit tests
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client,
                task_queue="test-design-queue",
                workflows=[MayorWorkflow],
                activities=[
                    mock_ba_design,
                    mock_architect_design,
                    mock_domain_experts,
                    mock_quarterback_synthesis,
                    mock_read_bead
                ],
                workflow_runner=UnsandboxedWorkflowRunner()
            ):
                result = await env.client.execute_workflow(
                    MayorWorkflow.run,
                    args=["test-bead-69", "Design"],
                    id="test-design-run",
                    task_queue="test-design-queue",
                )

                self.assertEqual(result, "Synthesis Success")
                print("\n✅ Meta-Testing Evidence: Design Workflow successfully orchestrated agents.")

if __name__ == "__main__":
    unittest.main()
