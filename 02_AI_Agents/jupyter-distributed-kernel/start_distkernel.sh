#!/bin/bash
# Start DistKernel Notebook in 24/7 mode with auto-restart

cd "$(dirname "$0")"

# Create logs directory
mkdir -p logs

# Log file with timestamp
LOG_FILE="logs/distkernel_$(date +%Y%m%d_%H%M%S).log"

echo "Starting DistKernel Notebook..."
echo "Log file: $LOG_FILE"
echo "Press Ctrl+C to stop"

# Run with auto-restart enabled
python3 distkernel_notebook.py --host 0.0.0.0 --port 8555 >> "$LOG_FILE" 2>&1
