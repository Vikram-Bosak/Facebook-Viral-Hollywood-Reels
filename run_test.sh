#!/bin/bash
source venv/bin/activate
echo "Starting End-to-End Test for Viral Hollywood Reel..."
echo "-----------------------------------------------------"
echo "Step 1: Running Agent 1 (Downloader)..."
python3 -u src/agent_1_downloader.py

echo "-----------------------------------------------------"
echo "Step 2: Running Agent 2 (Editor)..."
python3 -u src/agent_2_editor.py

echo "-----------------------------------------------------"
echo "Step 3: Running Agent 3 (Uploader)..."
python3 -u src/agent_3_uploader.py

echo "-----------------------------------------------------"
echo "Test Run Completed."
