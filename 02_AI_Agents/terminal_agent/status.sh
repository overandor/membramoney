#!/bin/bash
# Check the status of the Terminal Agent

cd "$(dirname "$0")")

if [ ! -f agent.pid ]; then
    echo "Agent is not running (no PID file)"
    exit 1
fi

PID=$(cat agent.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Agent is running (PID: $PID)"
    echo ""
    echo "Recent logs:"
    if [ -f logs/terminal_agent_$(date +%Y%m%d).log ]; then
        tail -n 20 logs/terminal_agent_$(date +%Y%m%d).log
    else
        echo "No log file for today"
    fi
else
    echo "Agent is not running (stale PID file)"
    exit 1
fi
