#!/bin/bash
set -e
cd /root/empire_os
# Kill previous hub processes
pkill -f "python3 -m empire_os.hub" 2>/dev/null || true
sleep 2
# Clear any zombie state
rm -f /var/run/hub.pid
# Create logs directory
mkdir -p logs
# Start hub with proper logging
nohup python3 -m empire_os.hub --host 0.0.0.0 --port 8081 >> logs/hub.log 2>&1 &
HUB_PID=$!
echo "Started hub with PID: $HUB_PID"
sleep 3
# Check if hub is running
if kill -0 $HUB_PID 2>/dev/null; then
    echo "Hub is running!"
    curl -s http://127.0.0.1:8081/health
else
    echo "Hub failed to start"
    cat logs/hub.log
    exit 1
fi
