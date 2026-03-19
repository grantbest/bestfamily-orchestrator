# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is
Gastown — a Temporal-based multi-agent SDLC orchestrator. Vikunja tasks move through kanban buckets (Design → Doing → Validation → Done) and trigger AI agents via webhooks.

## Run / Restart
```bash
# Restart (picks up volume-mounted code changes without rebuild)
docker compose restart agent-orchestrator

# Rebuild image (only needed if dependencies change)
docker compose up -d --build agent-orchestrator

# Check logs
docker logs agent-orchestrator --tail=50
docker logs agent-orchestrator --tail=50 2>&1 | grep -E "(ERROR|Mayor|Polecat|Moved)"
```

## Key Architecture

### Temporal Workers (unified_orchestrator.py)
All registered in `src/workers/unified_orchestrator.py`. Five workers:
- `main-orchestrator-queue` — MayorWorkflow + MasterPipelineWorkflow + RefineryWorkflow + all mayor/refinery activities
- `architect-queue`, `sre-queue`, `betting-app-queue`, `homelab-queue` — specialist activities

### Workflow Rules (CRITICAL)
- **No I/O in `workflow.run()`** — HTTP calls, file ops, and Vikunja API must be in `@activity.defn` functions. Violations cause `[TMPRL1101] Potential deadlock detected`.
- All sync SDK calls in `model_router.py` must be wrapped in `asyncio.to_thread(_sync)`.

### Mayor Workflow Paths (`src/workers/mayor_workflow.py`)
- **Design**: BA scope → Architect design → Game Designer review → Domain experts → Quarterback synthesis → posts design doc + questions to Vikunja
- **DesignRefine**: Incorporates user comment reply into existing design
- **Doing (story)**: triage_task_queue → polecat_developer_activity → move to Validation
- **Doing (epic)**: mark_breakdown_started → breakdown → fan-out child workflows → move stories to Doing → asyncio.gather fan-in → clear marker → move epic to Validation
- **Validation**: RefineryWorkflow (lint → merge → integration test → cleanup → move to Done)

### Epic/Story Detection
- Epic: `[EPIC]` in title, or starts with `EPIC:` / `EPIC ` — also anything that is neither
- Story: `[STORY]` in title

## Anti-Loop Architecture (do not regress)
Three layers prevent the epic coordinator from restarting in a loop:

1. **No `link_beads` in `breakdown_activity`** — `link_beads` fires `task.updated` on the parent epic, re-triggering the coordinator after it completes. Removed entirely.

2. **Fan-out order**: `start_child_workflow` FIRST, then `move_task_activity` to Doing. When the webhook fires (from move_to_bucket), the child is already Running → webhook skips it.

3. **`[BREAKDOWN_STARTED]` marker**: The coordinator stamps this into the epic description as its first action. The webhook at `Homelab/scripts/webhook_listener.py` ignores all `task.updated` Doing events for tasks with this marker. Cleared by `clear_breakdown_marker_activity` before Validation move.

**Webhook deduplication**: `task.updated` bucket moves use deterministic IDs (`agile-task-{id}-{bucket}-entry`). If already ran, returns `skipped` — no timestamp fallback, no re-run.

## LLM Fallback Chain (`src/utils/model_router.py`)
Claude → Gemini → GPT-4 → Ollama (always final). All calls async via `asyncio.to_thread`.

## Polecat Developer (`src/workers/polecat_activities.py`)
- Stage 1: Docker Aider (fails in container — no docker socket mounted)
- Stage 2: Native File-Writer via ModelRouter
- Git worktree at `/tmp/polecats/polecat-{bead_id}`, branch `polecat/{bead_id}`
- Workspace env: `WORKSPACE_ROOT=/app` (container) or `/Users/grantbest/Documents/Active` (host fallback)

## Vikunja Integration (`Homelab/scripts/beads_manager.py`)
- `move_to_bucket()` uses `GET /projects/2/views/8/buckets` (Kanban view, NOT `/projects/2/buckets`)
- Bucket IDs: To-Do=4, Design=7, Doing=5, Validation=8, Done=6
- Project ID=2, Kanban View ID=8
- Token and IDs in `Homelab/shared-services/.env`

## Terminate a Runaway Workflow
```bash
docker exec temporal sh -c "temporal workflow terminate --workflow-id agile-task-170-doing-entry --address temporal:7233 --reason 'reason'"
docker exec temporal sh -c "temporal workflow list --address temporal:7233"
```

## Delete Loop-Created Vikunja Tasks
```bash
for i in $(seq 200 250); do
  curl -s -o /dev/null -w "DELETE $i: %{http_code}\n" -X DELETE \
    -H "Authorization: Bearer $VIKUNJA_API_TOKEN" \
    "https://tracker.bestfam.us/api/v1/tasks/$i"
done
```
