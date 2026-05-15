#!/bin/bash
# Check status of Collaborative Terminal Agent

cd "$(dirname "$0")"

if [ ! -f collab_agent.pid ]; then
    echo "Agent is not running (no PID file)"
    exit 1
fi

PID=$(cat collab_agent.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Agent is running (PID: $PID)"
    echo ""
    echo "Recent logs:"
    if [ -f logs/collab_agent_$(date +%Y%m%d).log ]; then
        tail -n 20 logs/collab_agent_$(date +%Y%m%d).log
    else
        echo "No log file for today"
    fi
else
    echo "Agent is not running (stale PID file)"
    rm collab_agent.pid
    exit 1
fi
