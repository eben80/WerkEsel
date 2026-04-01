#!/bin/bash

# --- WerkEsel EC2 Master Orchestrator ---
# Purpose: Score new jobs and generate PDFs for approved ones.

PROJECT_DIR="/home/ubuntu/job_agent"
VENV_PATH="$PROJECT_DIR/venv/bin/activate"

echo "------------------------------------------------"
echo "🧠 WerkEsel: Starting AI Processing Cycle..."
echo "------------------------------------------------"

# 1. Navigate to project
cd $PROJECT_DIR

# 2. Activate Virtual Environment
source $VENV_PATH

# 3. Run the Matcher (Scoring)
echo "🔍 Step 1: Running Matcher..."
python3 matcher.py

echo "------------------------------------------------"

# 4. Run the Tailor (PDF Generation)
echo "🧵 Step 2: Running Tailor..."
python3 tailor.py

echo "------------------------------------------------"
echo "✅ Cycle Complete. Check tefinitely.com/werkesel/"
echo "------------------------------------------------"
