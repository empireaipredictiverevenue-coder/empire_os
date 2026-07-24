#!/bin/bash
# /root/empire_os/start_empire_os.sh — Empire OS v3 Complete Startup
# Verified working 2026-07-24

export PYTHONPATH="/root/empire_os:/root/empire_os/empire_os:$PYTHONPATH"
cd /root/empire_os

# Kill stale processes
pkill -f "python.*empire_os.hub" 2>/dev/null
pkill -f "cortex_ai_assistant" 2>/dev/null
pkill -f "swarm.py" 2>/dev/null
pkill -f "crawler_runner" 2>/dev/null
sleep 3

# Phase 1: Hub API (Required First)
/root/venv/bin/python -c "
import uvicorn, sys
sys.path.insert(0, '.')
from empire_os.hub import app
uvicorn.run(app, host='0.0.0.0', port=8081, log_level='info', workers=1)
" &

# Phase 2: Intelligence Layer - Cortex AI Assistant
/root/venv/bin/python3 -m empire_os.agents.cortex_ai_assistant &

# Phase 3: Swarm Orchestration (inside empire-hub container)
incus exec empire-hub -- bash -c '
cd /root/agentic_revenue
/root/venv/bin/python3 swarm.py
' &

# Phase 4: Crawler / Lead Generation
/root/venv/bin/python3 -m empire_os.crawler_runner --metro NYC --source permits &

echo "Empire OS v3 started. Check: curl http://localhost:8081/health"