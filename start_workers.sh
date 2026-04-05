#!/bin/bash

# Configuration
export VIKUNJA_API_TOKEN=tk_12e196e19221fcf2a6c649a2e2ff41f4461d3f3e
export OPENAI_API_KEY=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
export ANTHROPIC_API_KEY=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
export GEMINI_API_KEY=AIzaSyCvf-tUysE2YDQmy6MQaxtl92nlndRUjQA
export TEMPORAL_ADDRESS=localhost:7233
export NATS_URL=nats://nats.bestfam.us:4222
export VIKUNJA_BASE_URL=http://localhost:3456/api/v1
export VIKUNJA_PROJECT_ID=2
export PIP_INDEX_URL=http://localhost:8082/nexus/repository/pypi-proxy/simple
export PIP_TRUSTED_HOST=localhost

# Paths
BASE_DIR="/Users/grantbest/Documents/Active/BestFam-Orchestrator"
VENV_PYTHON="$BASE_DIR/venv/bin/python3"
export PYTHONPATH="$BASE_DIR:$BASE_DIR/scripts:$BASE_DIR/src"

# Kill existing workers
pkill -f "_worker.py" || true
sleep 1

echo "🚀 Starting Mayor Worker..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/mayor_worker.py" > "$BASE_DIR/mayor.log" 2>&1 &

echo "🚀 Starting Polecat Worker (Betting App)..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/polecat_worker.py" > "$BASE_DIR/polecat.log" 2>&1 &

echo "🚀 Starting Polecat Worker (Homelab)..."
POLECAT_QUEUE=homelab-queue nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/polecat_worker.py" > "$BASE_DIR/polecat_homelab.log" 2>&1 &

echo "🚀 Starting Refinery Worker..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/refinery_worker.py" > "$BASE_DIR/refinery.log" 2>&1 &

echo "🚀 Starting SRE Worker (Monitoring)..."
nohup "$VENV_PYTHON" "$BASE_DIR/src/workers/sre_worker.py" > "$BASE_DIR/sre.log" 2>&1 &

echo "🚀 Starting NATS Continuity Subscriber (MacBook Catch-up)..."
nohup "$VENV_PYTHON" "/Users/grantbest/Documents/Active/BettingApp/scripts/nats_continuity.py" > "/Users/grantbest/Documents/Active/BettingApp/nats.log" 2>&1 &

echo "✨ Workers launched. Checking status..."
sleep 2
ps aux | grep _worker.py | grep -v grep
