#!/bin/bash
# Start the Terminal Agent in background with nohup

cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if agent is already running
if [ -f agent.pid ]; then
    PID=$(cat agent.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Agent is already running with PID $PID"
        exit 1
    else
        echo "Removing stale PID file"
        rm agent.pid
    fi
fi

# Check for port argument
PORT=${1:-5000}

# Start the agent in background with web server enabled
nohup python3 agent.py --web --port $PORT > logs/agent_stdout.log 2>&1 &
echo $! > agent.pid

echo "Terminal Agent started with PID $!"
echo "Web interface: http://0.0.0.0:$PORT"
echo "Web terminal: http://0.0.0.0:$PORT/terminal"
echo "Logs: logs/terminal_agent_$(date +%Y%m%d).log"
echo "To stop: ./stop_agent.sh"
echo "To view logs: tail -f logs/terminal_agent_$(date +%Y%m%d).log"
