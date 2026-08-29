#!/usr/bin/env bash
# Empire OS v3 — in-container core + product startup (idempotent, non-destructive)
# Supervisor.py owns the agent fleet (raw procs); this only brings up the
# systemd-managed core, timers, and the revenue-product daemons, and never
# double-spawns supervisor agents.
set -u
HUB_HEALTH="http://127.0.0.1:8081/v1/health/deep"
OMEGA="http://127.0.0.1:9100/getStatus"
TELE="http://127.0.0.1:9101/health"
SAT="http://127.0.0.1:9102/"
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }

start_svc(){ local s="$1"; local st; st=$(systemctl is-active "$s" 2>/dev/null); if [ "$st" != "active" ]; then log "start $s"; systemctl start "$s" 2>&1 | tail -1; else log "skip $s (active)"; fi; }
enable_timer(){ local t="$1"; systemctl enable "$t" >/dev/null 2>&1; local st; st=$(systemctl is-active "$t" 2>/dev/null); if [ "$st" != "active" ]; then systemctl start "$t" 2>&1 | tail -1; log "arm $t"; fi; }

# 1) Core systemd services
CORE_SVCS="empire-hub-8081 empire-supervisor empire-omega-learning empire-ppc-telephony-webhook empire-bsc-listener empire-solana-listener empire-settlement-gateway empire-outbox-reaper empire-inbound-reply-daemon empire-telegram-pro empire-unified-delivery empire-ppc-router empire-business-ops empire-billing-collector empire-content-engine empire-last30days-agent empire-strategist-agent empire-storm-predictor empire-verify-loop empire-a2a-sales-agent empire-mcp empire-lead-sniper-agent empire-outreach-runner empire-billing-collector-agent empire-mrr-billing"
for s in $CORE_SVCS; do start_svc "$s"; done

# 2) Timers
TIMERS="empire-crawler-runner.timer empire-a2a-sales-agent.timer empire-cortex-engine.timer empire-health-deep.timer empire-health-guard.timer empire-inbox-reaper.timer empire-last30days.timer empire-lead-rotator.timer empire-payout-scheduler.timer empire-prospect-scorer.timer empire-quote-reaper.timer empire-recovery-sequence.timer empire-revenue-digest.timer empire-revenue-snapshot.timer empire-revenue-watchdog.timer empire-rnd-agent.timer empire-settle-funnel.timer empire-settlement-gateway.timer empire-strategist-agent.timer empire-unified-delivery.timer empire-vault-guard.timer empire-wal-checkpoint.timer empire-watchdog.timer empire-ai-intel.timer empire-business-agent.timer empire-ceo-agent.timer empire-company-intel.timer empire-content-engine.timer empire-enrich.timer empire-funnel-closeout.timer empire-indexnow.timer empire-innovator.timer empire-intel-market.timer empire-intelligence.timer empire-lease-renewal.timer empire-mrr-billing.timer empire-nurture.timer"
for t in $TIMERS; do enable_timer "$t"; done

# 3) Revenue-product daemons (NOT supervisor-managed; idempotent via pgrep)
launch_daemon(){ local name="$1"; local match="$2"; local cmd="$3"; if pgrep -f "$match" >/dev/null; then log "skip $name (running)"; else log "launch $name"; nohup bash -c "$cmd" >/root/empire_os/logs/${name}.log 2>&1 & sleep 2; fi; }
mkdir -p /root/empire_os/logs
# satellite_service now managed by systemd (empire-satellite-service.service) — port 9102
start_svc "empire-satellite-service"
launch_daemon "a2a_buyer_marketplace" "a2a_buyer_marketplace.py --daemon" "/root/venv/bin/python3 -u /root/empire_os/empire_os/a2a_buyer_marketplace.py --daemon --interval 300"
# seat corridors (A2A seat layer) — run as one-shot seat/route reconcile
if ! pgrep -f "seat_corridors.py" >/dev/null; then
  log "reconcile seat_corridors (dryrun-route)"
  nohup /root/venv/bin/python3 -u /root/empire_os/empire_os/seat_corridors.py dryrun-route --sample 200 >/root/empire_os/logs/seat_corridors.log 2>&1 &
fi

# 4) Health gates
wait_url(){ local u="$1" n=0; while [ $n -lt 30 ]; do curl -sf "$u" >/dev/null 2>&1 && { log "OK $u"; return 0; }; sleep 2; n=$((n+1)); done; log "TIMEOUT $u"; }
wait_url "$HUB_HEALTH"
wait_url "$OMEGA"
wait_url "$TELE"
wait_url "$SAT"

# 5) Supervisor alive?
if ! pgrep -f "supervisor.py" >/dev/null; then log "WARN supervisor.py not running — starting"; systemctl start empire-supervisor; fi

log "core + product startup complete"
