#!/bin/bash

# BestFam Orchestrator Bootstrap Script
# Goal: Standardized local setup for humans and agents.

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "=========================================="
echo -e "🤖 BestFam-Orchestrator Setup"
echo "=========================================="

# 1. Python Venv
echo -e "${GREEN}[1/3] Creating Virtual Environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# 2. Dependencies
echo -e "${GREEN}[2/3] Installing Dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 3. Environment Check
echo -e "${GREEN}[3/3] Verifying Core Connectivity...${NC}"
# (Future: Add checks for Temporal/Ollama availability)

echo "=========================================="
echo -e "${GREEN}✅ BRAIN INITIALIZED${NC}"
echo -e "Run 'source venv/bin/activate' to start working."
echo "=========================================="
