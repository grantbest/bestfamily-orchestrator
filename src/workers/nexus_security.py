import asyncio
import os
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow, nexus, activity
import nexusrpc
import nexusrpc.handler

# --- Nexus Contract (The Service Interface) ---

@dataclass
class SecurityAuditInput:
    bead_id: str
    worktree_path: str
    repo_name: str

@dataclass
class SecurityAuditOutput:
    status: str
    findings: str
    audit_id: str

@nexusrpc.service(name="security-audit-service")
class SecurityAuditService:
    run_audit: nexusrpc.Operation[SecurityAuditInput, SecurityAuditOutput]

# --- Implementation ---

@activity.defn
async def run_security_scans_activity(path: str) -> str:
    """Mock security scan logic."""
    logging.info(f"🛡️ Nexus Security: Scanning {path}...")
    await asyncio.sleep(2)
    return "No high-severity vulnerabilities found. Gitleaks check: PASSED."

@workflow.defn
class SecurityAuditWorkflow:
    @workflow.run
    async def run(self, input: SecurityAuditInput) -> SecurityAuditOutput:
        findings = await workflow.execute_activity(
            run_security_scans_activity,
            input.worktree_path,
            start_to_close_timeout=timedelta(minutes=5)
        )
        return SecurityAuditOutput(
            status="SUCCESS",
            findings=findings,
            audit_id=workflow.info().workflow_id
        )

# --- Service Handler (The actual implementation of the service) ---

@nexusrpc.handler.service_handler(service=SecurityAuditService)
class SecurityAuditServiceHandler:
    @nexus.workflow_run_operation
    async def run_audit(self, ctx: nexus.WorkflowRunOperationContext, input: SecurityAuditInput) -> nexus.WorkflowHandle[SecurityAuditOutput]:
        return await ctx.start_workflow(
            SecurityAuditWorkflow.run,
            input,
            id=f"nexus-audit-{input.bead_id}-{uuid.uuid4().hex[:8]}",
            task_queue="modular-orchestrator-queue"
        )
