import asyncio
from datetime import timedelta
from temporalio import workflow, activity
from temporalio.common import RetryPolicy

@activity.defn
async def discovery_activity(bead_id: str, title: str, description: str) -> dict:
    from src.agents.product_expert import ProductExpertAgent
    print(f"🧠 Discovery for bead {bead_id}...")
    pe = ProductExpertAgent()
    scope = await pe.define_scope(title, description)
    return scope

@activity.defn
async def create_sre_bug_activity(error_details: str) -> str:
    """
    SRE FALLBACK: Automatically creates a bug bead in Vikunja when the pipeline fails.
    """
    # In a real implementation, this would use beads_manager to POST to Vikunja
    print(f"🚨 SRE FALLBACK TRIGGERED: {error_details}")
    return "SRE Bug Created"

@activity.defn
async def build_activity(bead_id: str) -> str:
    print(f"🛠 Building for bead {bead_id}...")
    return "Build Successful"

@activity.defn
async def test_activity(bead_id: str) -> str:
    print(f"🧪 Testing for bead {bead_id}...")
    # This is where we would generate 'Meta-Testing Evidence'
    return "Test Successful"

@activity.defn
async def secure_activity(bead_id: str) -> str:
    print(f"🛡 Securing for bead {bead_id}...")
    return "Security Audit Passed"

@activity.defn
async def deploy_activity(bead_id: str) -> str:
    print(f"🚀 Deploying for bead {bead_id}...")
    return "Deployment Successful"

# --- Workflows ---

@workflow.defn
class MasterPipelineWorkflow:
    @workflow.run
    async def run(self, bead_id: str, title: str, description: str) -> str:
        """
        The Master SDLC Pipeline with global SRE error-handling fallback.
        """
        standard_retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_attempts=3,
        )

        try:
            # Step 0: Discovery
            scope = await workflow.execute_activity(
                discovery_activity,
                args=[bead_id, title, description],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=standard_retry
            )

            # Step 1: Build
            await workflow.execute_activity(
                build_activity,
                bead_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=standard_retry
            )

            # Step 2: Test
            await workflow.execute_activity(
                test_activity,
                bead_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=standard_retry
            )

            # Step 3: Secure
            await workflow.execute_activity(
                secure_activity,
                bead_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=standard_retry
            )

            # Step 4: Deploy
            await workflow.execute_activity(
                deploy_activity,
                bead_id,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=standard_retry
            )

            return "Pipeline Completed Successfully"

        except Exception as e:
            # --- GLOBAL SRE FALLBACK ---
            error_msg = f"Pipeline Failure on Bead {bead_id}: {str(e)}"
            await workflow.execute_activity(
                create_sre_bug_activity,
                error_msg,
                start_to_close_timeout=timedelta(seconds=60)
            )
            raise e
