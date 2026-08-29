#!/bin/bash
# Empire OS v3 - Deploy R&D Agent Stack
# Installs and starts all systemd services for the continuous revenue loop

set -euo pipefail

echo "══════════════════════════════════════════════════════════════"
echo "Empire OS v3 - Deploying R&D Agent Stack"
echo "══════════════════════════════════════════════════════════════"

SERVICES_DIR="/root/empire_os/empire_os/agents/systemd"
SYSTEMD_DIR="/etc/systemd/system"

# Services to deploy
SERVICES=(
    "north_mini_agent.service"
    "whale_harvester.service"
    "outreach_runner.service"
    "rd_agent.service"
    "empire-nurture.service"
    "supervisor.service"
)

echo ""
echo "📋 Copying service files to /etc/systemd/system..."
for svc in "${SERVICES[@]}"; do
    if [[ -f "$SERVICES_DIR/$svc" ]]; then
        cp "$SERVICES_DIR/$svc" "$SYSTEMD_DIR/"
        echo "  ✓ $svc"
    else
        echo "  ⚠ $svc not found, skipping"
    fi
done

echo ""
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

echo ""
echo "🚀 Enabling services..."
for svc in "${SERVICES[@]}"; do
    systemctl enable "$svc" 2>/dev/null && echo "  ✓ $svc enabled" || echo "  ⚠ $svc enable failed"
done

echo ""
echo "▶️  Starting services..."
for svc in "${SERVICES[@]}"; do
    systemctl restart "$svc" 2>/dev/null && echo "  ✓ $svc started" || echo "  ⚠ $svc start failed"
done

echo ""
echo "📊 Service status:"
for svc in "${SERVICES[@]}"; do
    systemctl is-active "$svc" 2>/dev/null && echo "  ✓ $svc: ACTIVE" || echo "  ✗ $svc: INACTIVE"
done

echo ""
echo "📜 Recent logs (last 20 lines each):"
for svc in "${SERVICES[@]}"; do
    echo "  ── $svc ──"
    journalctl -u "$svc" -n 5 --no-pager 2>/dev/null || echo "    (no logs yet)"
done

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "Deployment complete! R&D Agent stack is running."
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "Key endpoints to monitor:"
echo "  - R&D Agent report: cat /root/feedback/rd_report.json"
echo "  - R&D Agent logs:   journalctl -u rd_agent -f"
echo "  - North Mini plans: cat /root/feedback/north_mini_plans.jsonl"
echo "  - Whale harvest:    cat /root/feedback/whales_harvested.jsonl"
echo "  - Outreach logs:    cat /root/empire_os/logs/outreach_log.jsonl"
echo "  - Lead deliveries:  cat /root/feedback/lead_deliveries.jsonl"
echo ""
echo "Revenue loop flow:"
echo "  north_mini_agent (strategy) → reads → northmini_realstate (truth)"
echo "                                      ↓"
echo "  enterprise_campaigns (create) → outbound_campaigns (draft)"
echo "                                      ↓"
echo "  campaigns.launch() → lead_deliverer_agent.tick_once() → delivery + billing"
echo "                                      ↓"
echo "  whale_harvester → si_prospect_consent (WHALE tier) → Chief of Staff dials"
echo "══════════════════════════════════════════════════════════════"