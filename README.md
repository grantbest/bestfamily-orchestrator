# 🤖 Agent Orchestrator

This application is the central "Command Center" for the BestFam multi-agent ecosystem. It manages the full SDLC: Triage, Design, Implementation, Security, and Deployment.

## ⚖️ Strict SDLC & Agile Mandate
All development in this repository MUST follow these rules:

1. **Bead Integration**: Every unit of work must be tied to a Bead (Issue).
2. **Type-Safe Workers**: All Temporal Workers must use strict Python typing (Pydantic/MyPy).
3. **Meta-Testing Mandate**: 
    - Every Story must contain **Testing Evidence**.
    - Evidence must be stored in `tests/evidence/<bead_id>/`.
    - Evidence includes: Pytest outputs, LLM-reasoning traces, or Screenshot/Log diffs.
    - The Pipeline will FAIL if evidence is not found for a Story.
4. **Global SRE Fallback**: All workflows must wrap their execution in a global try/catch that triggers the `CreateSREBugActivity` on failure.

## 🏗 Folder Structure
- `src/api`: FastAPI webhooks and REST endpoints.
- `src/workers`: Temporal worker definitions.
- `src/agents`: specialized LLM agent logic (BA, SRE, etc).
- `src/tools`: Reusable tools (grep, replace, build, etc).
- `tests/`: Automated test suites.
- `tests/evidence/`: Repository for meta-testing artifacts.
