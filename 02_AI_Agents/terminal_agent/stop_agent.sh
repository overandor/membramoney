#!/bin/bash
# Stop the Terminal Agent

cd "$(dirname "$0")"

if [ ! -f agent.pid ]; then
    echo "No PID file found. Agent may not be running."
    exit 1
fi

PID=$(cat agent.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping Terminal Agent (PID: $PID)..."
    kill $PID
    
    # Wait for process to stop
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            echo "Agent stopped successfully"
            rm agent.pid
            exit 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    echo "Force killing agent..."
    kill -9 $PID
    rm agent.pid
    echo "Agent force stopped"
else
    echo "Agent process not found (PID: $PID)"
    rm agent.pid
    exit 1
fi
