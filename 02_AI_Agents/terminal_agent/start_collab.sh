#!/bin/bash
# Start the Collaborative Terminal Agent

cd "$(dirname "$0")"

# Create logs directory
mkdir -p logs

# Check if already running
if [ -f collab_agent.pid ]; then
    PID=$(cat collab_agent.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Agent already running with PID $PID"
        exit 1
    else
        rm collab_agent.pid
    fi
fi

# Export Gate.io API credentials
export GATE_API_KEY=57897b69c76df6aa01a1a25b8d9c6bc8
export GATE_API_SECRET=ed43f2696c3767685e8470c4ba98ea0f7ea85e9adeb9c3d098182889756d79d9

# Start Ollama if not running
if ! pgrep -f "ollama serve" > /dev/null; then
    echo "Starting Ollama..."
    ollama serve > /dev/null 2>&1 &
    sleep 2
    echo "Ollama started"
else
    echo "Ollama already running"
fi

# Port argument
PORT=${1:-5000}

# Start agent
nohup python3 collab_agent.py --web --port $PORT > logs/collab_agent_stdout.log 2>&1 &
echo $! > collab_agent.pid

echo "Collaborative Terminal Agent started with PID $!"
echo "Web interface: http://0.0.0.0:$PORT/terminal"
echo "Default login: admin / admin123 (CHANGE THIS!)"
echo "Logs: logs/collab_agent_$(date +%Y%m%d).log"
echo "To stop: ./stop_collab.sh"
