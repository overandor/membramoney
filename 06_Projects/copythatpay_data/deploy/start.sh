#!/bin/bash
# CopyThatPay — tmux launcher script
# Usage: ./start.sh
# To reconnect later: tmux attach -t copythatpay

SESSION="copythatpay"
BOT_DIR="/Users/alep/Downloads"
PYTHON="/Users/alep/miniconda3/bin/python"
BOT="copythatpay.py"

# Create log directory
mkdir -p "$BOT_DIR/copythatpay_data/logs"

# Kill existing session if running
tmux has-session -t "$SESSION" 2>/dev/null && {
    echo "Session '$SESSION' already running. Attach with: tmux attach -t $SESSION"
    exit 0
}

# Start new tmux session with the bot
tmux new-session -d -s "$SESSION" -c "$BOT_DIR" "$PYTHON $BOT 2>&1 | tee copythatpay_data/logs/bot_$(date +%Y%m%d_%H%M%S).log"

echo "CopyThatPay started in tmux session '$SESSION'"
echo "Attach:  tmux attach -t $SESSION"
echo "Detach:  Ctrl+B then D"
echo "Stop:    tmux kill-session -t $SESSION"
