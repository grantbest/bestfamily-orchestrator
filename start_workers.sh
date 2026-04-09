#!/bin/bash

# Configuration
# Secrets are loaded via EnvLoader.py or OS environment
export TEMPORAL_ADDRESS=localhost:7233
export NATS_URL=nats://nats.bestfam.us:4222
export VIKUNJA_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzU2NTU3MjgsImlkIjoxLCJqdGkiOiI4ODFmNDRmZC01NWI1LTQwOWEtOWI3Zi1kNWZiMThkOWUzODciLCJzaWQiOiI0ZTBlNTkyZS0zY2VlLTQ1MWMtYTVkYy1kZTc1ZmFmYWRjMDIiLCJ0eXBlIjoxLCJ1c2VybmFtZSI6ImFkbWluIn0.KyLvYwB5PeOwssJV6ok1Gg9rW7lvoLx_3fe7zZ0ueUc
export VIKUNJA_BASE_URL=http://localhost:3456/api/v1
export VIKUNJA_PROJECT_ID=1
export ENABLE_VIKUNJA=true
export DB_HOST=35.238.57.237
export OLLAMA_BASE_URL=http://localhost:11434

# LLM API Keys for ModelRouter
export GEMINI_API_KEY=AIzaSyCvf-tUysE2YDQmy6MQaxtl92nlndRUjQA
export OPENAI_API_KEY=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
export ANTHROPIC_API_KEY=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

export PIP_INDEX_URL=http://localhost:8082/nexus/repository/pypi-proxy/simple
export PIP_TRUSTED_HOST=localhost

# Paths
BASE_DIR="/Users/grantbest/Documents/Active/BestFam-Orchestrator"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"
export PYTHONPATH="$BASE_DIR:$BASE_DIR/scripts:$BASE_DIR/src"

# Kill existing workers
pkill -9 -f "_worker.py" || true
pkill -9 -f "_worker_standalone.py" || true
pkill -9 -f "nats_continuity.py" || true
pkill -9 -f "unified_orchestrator.py" || true
pkill -9 -f "webhook_listener.py" || true
pkill -9 -f "sidecar.py" || true
sleep 1

echo "🚀 Starting Gastown Resiliency Sidecar (IDP/Proxy)..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/utils/sidecar.py" > "$BASE_DIR/sidecar.log" 2>&1 &
sleep 2 # Wait for sidecar to bind

# --- SRE: INFRASTRUCTURE REFINERY GATE ---
echo "🧪 Running Infrastructure Pre-Flight Check..."
if ! "$VENV_PYTHON" "$BASE_DIR/scripts/pre_flight_check.py"; then
    echo "❌ PRE-FLIGHT CHECK FAILED. Infrastructure is unstable. Check logs."
    pkill -9 -f "sidecar.py"
    exit 1
fi
echo "✅ Infrastructure Linted."

echo "🚀 Starting Gastown Orchestrator (Design/Breakdown) in 'default'..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/unified_orchestrator.py" --worker-type orchestrator --namespace default > "$BASE_DIR/orchestrator.log" 2>&1 &

echo "🚀 Starting Polecat Developer (Implementation Loop) in 'betting-app'..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/unified_orchestrator.py" --worker-type developer --namespace betting-app > "$BASE_DIR/developer.log" 2>&1 &

echo "🚀 Starting Homelab Worker (Infrastructure/Refinery) in 'homelab'..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/unified_orchestrator.py" --worker-type homelab --namespace homelab > "$BASE_DIR/homelab_worker.log" 2>&1 &

echo "🚀 Starting Vikunja Webhook Listener (Dispatcher)..."
nohup "$VENV_PYTHON" "/Users/grantbest/Documents/Active/Homelab/scripts/webhook_listener.py" > "/Users/grantbest/Documents/Active/Homelab/webhook.log" 2>&1 &

echo "🚀 Starting NATS Continuity Subscriber..."
nohup "$VENV_PYTHON" "/Users/grantbest/Documents/Active/BettingApp/scripts/nats_continuity.py" > "/Users/grantbest/Documents/Active/BettingApp/nats.log" 2>&1 &

echo "✨ Gastown v3.5 Launched. Monitoring unified.log..."
sleep 2
ps aux | grep -E "unified_orchestrator|webhook_listener" | grep -v grep

