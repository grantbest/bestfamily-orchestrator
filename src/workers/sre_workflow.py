import asyncio
import os
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
with workflow.unsafe.imports_passed_through():
    from src.workers.sre_activities import (
        sre_site_monitor_activity,
        sre_check_vikunja_bugs_activity,
        sre_check_temporal_health_activity,
        sre_log_audit_activity,
        sre_remediate_issue_activity
    )

@workflow.defn
class SREHealingWorkflow:
    @workflow.run
    async def run(self) -> None:
        """
        GASTOWN SRE: Continuous Self-Healing Loop.
        Runs every 30 minutes to ensure system stability.
        """
        retry = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        
        while True:
            # 1. Check Site Health
            await workflow.execute_activity(
                sre_site_monitor_activity,
                args=["https://bestfam.us"],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry
            )

            # 2. Audit System Logs (Next.js locks, 500s)
            await workflow.execute_activity(
                sre_log_audit_activity,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry
            )

            # 3. Check Temporal for stale workflows (> 4 hours)
            await workflow.execute_activity(
                sre_check_temporal_health_activity,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry
            )

            # 4. Check for manually created SRE incidents (If Vikunja is enabled)
            if os.getenv("ENABLE_VIKUNJA", "true").lower() == "true":
                bugs = await workflow.execute_activity(
                    sre_check_vikunja_bugs_activity,
                    start_to_close_timeout=timedelta(minutes=1),
                    retry_policy=retry
                )

                for bug in bugs:
                    await workflow.execute_activity(
                        sre_remediate_issue_activity,
                        args=[bug],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=retry
                    )

            # Wait 30 minutes before next iteration
            await asyncio.sleep(1800)
