#!/bin/bash

# --- WerkEsel Multi-User Master Orchestrator ---
# Purpose: Run the full workflow for all users and profiles.

PROJECT_DIR="/home/ubuntu/job_agent"
VENV_PATH="$PROJECT_DIR/venv/bin/activate"

echo "------------------------------------------------"
echo "🫏 WerkEsel: Starting Multi-User AI Processing Cycle..."
echo "------------------------------------------------"

cd $PROJECT_DIR
# source $VENV_PATH # Uncomment if using venv

python3 run_all.py

echo "------------------------------------------------"
echo "✅ Cycle Complete."
echo "------------------------------------------------"
