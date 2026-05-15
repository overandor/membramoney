#!/bin/bash
# Stop the Collaborative Terminal Agent

cd "$(dirname "$0")"

if [ ! -f collab_agent.pid ]; then
    echo "No PID file found"
    exit 1
fi

PID=$(cat collab_agent.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping agent (PID: $PID)..."
    kill $PID
    
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            echo "Agent stopped"
            rm collab_agent.pid
            exit 0
        fi
        sleep 1
    done
    
    kill -9 $PID
    rm collab_agent.pid
    echo "Agent force stopped"
else
    echo "Agent not running"
    rm collab_agent.pid
fi
