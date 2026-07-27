#!/bin/bash
# /root/empire_os/start_empire_os_full.sh — Empire OS v3 Complete Startup
# Verified working 2026-07-25 | Background mode with full state capture

set -euo pipefail

export PYTHONPATH="/root/empire_os:/root/empire_os/empire_os:$PYTHONPATH"
cd /root/empire_os

LOG_DIR="/root/empire_os/logs"
FEEDBACK_DIR="/root/feedback"
GBRAIN_DIR="/root/g-brain/system"

mkdir -p "$LOG_DIR/hub" "$LOG_DIR/agents" "$FEEDBACK_DIR" "$GBRAIN_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
STARTUP_LOG="$FEEDBACK_DIR/startup_${TIMESTAMP}.log"

exec > >(tee -a "$STARTUP_LOG") 2>&1

echo "=== EMPIRE OS v3 FULL STARTUP - $TIMESTAMP ==="

# ────────────────────────────────────────────────────────────────
# PHASE 0: Kill stale processes
# ────────────────────────────────────────────────────────────────
echo "[Phase 0] Killing stale processes..."
pkill -f "empire_os.hub" 2>/dev/null || true
pkill -f "intelligence_loop" 2>/dev/null || true
pkill -f "crawler_runner" 2>/dev/null || true
pkill -f "lane_monitor" 2>/dev/null || true
pkill -f "cortex_engine" 2>/dev/null || true
pkill -f "lead_sniper_agent" 2>/dev/null || true
pkill -f "solana_listener" 2>/dev/null || true
sleep 3

# ────────────────────────────────────────────────────────────────
# PHASE 1: Hub API (Required First) - runs in empire-hub container
# ────────────────────────────────────────────────────────────────
echo "[Phase 1] Starting Hub API in empire-hub container..."
incus exec empire-hub -- bash -c "
mkdir -p /root/empire_os/logs/hub
cd /root/empire_os
export EMPIRE_PORT=8081
export EMPIRE_HOST=0.0.0.0
/root/venv/bin/python3 -m empire_os.hub > /root/empire_os/logs/hub/hub.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8081/health
" || true

# ────────────────────────────────────────────────────────────────
# PHASE 2: Intelligence Layer (Host-level agents)
# ────────────────────────────────────────────────────────────────
echo "[Phase 2] Starting Intelligence Layer (host)..."

# Intelligence Loop - core lead processing
nohup /root/venv/bin/python3 -m empire_os.intelligence_loop \
  > "$LOG_DIR/agents/intelligence_loop.log" 2>&1 &
IL_PID=$!
echo "Intelligence Loop PID: $IL_PID"

# North Mini Agent - customer intelligence
nohup /root/venv/bin/python3 /root/empire_os/empire_os/north_mini_agent.py \
  > "$LOG_DIR/agents/north_mini_agent.log" 2>&1 &
NMA_PID=$!
echo "North Mini Agent PID: $NMA_PID"

# CEO Agent - OKF vision
nohup /root/hunt_venv/bin/python -u /root/empire_os/ceo_agent.py \
  > "$LOG_DIR/agents/ceo_agent.log" 2>&1 &
CEO_PID=$!
echo "CEO Agent PID: $CEO_PID"

# Chief of Staff - orchestrator
nohup /root/hunt_venv/bin/python -u /root/empire_os/chief_of_staff.py \
  > "$LOG_DIR/agents/chief_of_staff.log" 2>&1 &
COS_PID=$!
echo "Chief of Staff PID: $COS_PID"

# Deep Research Agent - A2A/AEO research
nohup /root/hunt_venv/bin/python -u /root/empire_os/deep_research_agent.py \
  > "$LOG_DIR/agents/deep_research_agent.log" 2>&1 &
DRA_PID=$!
echo "Deep Research Agent PID: $DRA_PID"

# ────────────────────────────────────────────────────────────────
# PHASE 3: Crawler & Lead Generation (empire-hub container)
# ────────────────────────────────────────────────────────────────
echo "[Phase 3] Starting Crawler & Lead Generation in empire-hub..."

incus exec empire-hub -- bash -c "
cd /root/empire_os
# Crawler Runner
nohup /root/venv/bin/python3 -m empire_os.crawler_runner --metro NYC --source permits \
  > /root/empire_os/logs/crawler.log 2>&1 &
echo \"Crawler PID: \$!\"

# Lane Monitor
nohup /root/venv/bin/python3 /root/empire_os/empire_os/lane_monitor.py \
  > /root/empire_os/logs/lane_monitor.log 2>&1 &
echo \"Lane Monitor PID: \$!\"

# Lead Sniper Agent
nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/lead_sniper_agent.py \
  > /root/empire_os/logs/lead_sniper.log 2>&1 &
echo \"Lead Sniper PID: \$!\"

# Predictive Agent
nohup /root/venv/bin/python3 -m empire_os.agents.predictive_agent \
  > /root/empire_os/logs/predictive_agent.log 2>&1 &
echo \"Predictive Agent PID: \$!\"
" || true

# ────────────────────────────────────────────────────────────────
# PHASE 4: Empire-Hub Container Agents
# ────────────────────────────────────────────────────────────────
echo "[Phase 4] Starting Empire-Hub Container Agents..."

incus exec empire-hub -- bash -c "
cd /root/empire_os
# Solana Listener Agent
nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/solana_listener_agent.py \
  > /root/empire_os/logs/solana_listener.log 2>&1 &
echo \"Solana Listener PID: \$!\"

# Cortex Engine - periodic intelligence
nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/cortex_engine.py \
  > /root/empire_os/logs/cortex_engine.log 2>&1 &
echo \"Cortex Engine PID: \$!\"

# Swarm Orchestration
nohup /root/venv/bin/python3 /root/agentic_revenue/swarm.py \
  > /root/empire_os/logs/swarm.log 2>&1 &
echo \"Swarm PID: \$!\"
" || true

# ────────────────────────────────────────────────────────────────
# PHASE 5: Lead Sniper Agent Container
# ────────────────────────────────────────────────────────────────
echo "[Phase 5] Starting Lead Sniper Container..."
incus exec lead-sniper-agent -- bash -c "
nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/lead_sniper_agent.py \
  > /root/empire_os/logs/lead_sniper_container.log 2>&1 &
echo \"Lead Sniper Container PID: \$!\"
" || true

# ────────────────────────────────────────────────────────────────
# PHASE 6: Verification & State Capture
# ────────────────────────────────────────────────────────────────
echo "[Phase 6] Verification & State Capture..."
sleep 5

# Verify Hub
echo "=== Hub Health ==="
curl -s http://10.118.155.218:8081/health | python3 -m json.tool
curl -s http://10.118.155.218:8081/v1/health/deep | python3 -m json.tool

# Capture cortex report
if [ -f "$FEEDBACK_DIR/cortex_report.json" ]; then
  cp "$FEEDBACK_DIR/cortex_report.json" "$GBRAIN_DIR/cortex_report_${TIMESTAMP}.json"
  echo "Cortex report captured"
fi

# Capture crawler stats
curl -s http://10.118.155.218:8081/v1/crawler/stats | python3 -m json.tool > "$GBRAIN_DIR/crawler_stats_${TIMESTAMP}.json"

# Capture lead counts
curl -s http://10.118.155.218:8081/v1/leads/counts | python3 -m json.tool > "$GBRAIN_DIR/lead_counts_${TIMESTAMP}.json"

# Process snapshot
ps aux | grep -E "(python|empire)" | grep -v grep > "$GBRAIN_DIR/process_snapshot_${TIMESTAMP}.txt"

# Container status
incus list -c n,s,4,6 > "$GBRAIN_DIR/container_status_${TIMESTAMP}.txt"

# Summary state
cat > "$GBRAIN_DIR/system_state_${TIMESTAMP}.json" << EOJ
{
  "timestamp": "$TIMESTAMP",
  "startup_log": "$STARTUP_LOG",
  "pids": {
    "intelligence_loop": $IL_PID,
    "north_mini_agent": $NMA_PID,
    "ceo_agent": $CEO_PID,
    "chief_of_staff": $COS_PID,
    "deep_research_agent": $DRA_PID
  },
  "containers": [
    "empire-hub", "twenty-crm", "documenso", "formbricks-survey",
    "listmonk-mail", "post-analytics", "appsmith-admin", "lead-sniper-agent"
  ],
  "status": "STARTED"
}
EOJ

echo ""
echo "=== EMPIRE OS v3 STARTUP COMPLETE ==="
echo "Startup log: $STARTUP_LOG"
echo "System state: $GBRAIN_DIR/system_state_${TIMESTAMP}.json"
echo ""
echo "Key verification endpoints:"
echo "  curl http://10.118.155.218:8081/health"
echo "  curl http://10.118.155.218:8081/v1/health/deep"
echo "  curl http://10.118.155.218:8081/v1/crawler/stats"
echo "  curl http://10.118.155.218:8081/v1/leads/counts"