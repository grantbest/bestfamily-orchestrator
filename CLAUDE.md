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
```

## Key Architecture

### Temporal Workers (unified_orchestrator.py)
All registered in `src/workers/unified_orchestrator.py`. Four main agents: Mayor, Polecat, Refinery, SRE.

### Workflow Rules
- **No I/O in `workflow.run()`** — Use `@activity.defn`.
- All sync SDK calls in `model_router.py` must be wrapped in `asyncio.to_thread(_sync)`.

### LLM Priority (`src/utils/model_router.py`)
Gemini (Flash/2.0) → OpenAI (GPT-4o) → Ollama (always final).

### Polecat Developer Agent
- **Native File-Writer**: Reads context from workspace files before implementation.
- **Verification Gate**: Captures `pytest` output as evidence in `tests/evidence/{bead_id}/`.
- Isolated via Git worktree at `/tmp/polecats/polecat-{bead_id}`.

### Refinery Integration Gate
- **Evidence Gate**: Rejects work if `pytest_output.txt` is missing from the evidence directory.
- **Quality Gate**: Runs Ruff for linting and formatting.
- **Integration Crucible**: Runs full test suite after merge, with automatic rollback on failure.

### Vikunja Integration (beads_manager.py)
- Uses REST API for all task management.
- Project ID=2, Kanban View ID=8.
- Status to Bucket mapping: Pending=To-Do, Triaged=Design, Running=Doing, Done=Done.

## Terminate a Runaway Workflow
```bash
docker exec temporal sh -c "temporal workflow terminate --workflow-id agile-task-170-doing-entry --address temporal:7233"
```
