#!/bin/bash

# Full end-to-end test with mock CleanStat server

echo "Starting Mock CleanStat Server..."
python mock_cleanstat_server.py &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Failed to start mock server"
    exit 1
fi

echo "✓ Mock server running on http://localhost:8000"
echo ""

# Run the vertical slice test
echo "Running vertical slice test..."
python test_vertical_slice.py

# Capture exit code
TEST_EXIT=$?

# Stop the mock server
kill $SERVER_PID 2>/dev/null

echo ""
echo "Mock server stopped"

exit $TEST_EXIT
