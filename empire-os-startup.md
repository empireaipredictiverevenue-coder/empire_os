# Empire OS v3 — Enhanced Startup Guide

**Generated**: 2026-07-28T23:15Z
**Status**: LIVE — all core services operational

---

## 1. ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────┐
│                  EMPIRE OS v3 CORE                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌─────────────────┐  │
│  │ LANE     │   │SWITCH-   │   │PPC ROUTER       │  │
│  │ ROUTER   │──▶│ BOARD    │──▶│ :9200           │  │
│  │ (keyword)│   │ :9100    │   │ 5-headed billing│  │
│  └──────────┘   └──────────┘   └────────┬────────┘  │
│        │                                 │          │
│        ▼                                 ▼          │
│  ┌──────────┐                     ┌──────────────┐  │
│  │CAMPAIGNS │                     │CHARGE ADAPTER│  │
│  │(8 live)  │                     │(Stripe→USDC) │  │
│  └──────────┘                     └──────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │         INCUS CONTAINER FLEET (live)         │   │
│  │  empire-hub (8081)  twenty-crm  documenso    │   │
│  │  formbricks-survey  graphify  post-analytics │   │
│  │  appsmith-admin     listmonk-mail             │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 2. RUNNING SERVICES

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| **Empire Hub** | :8081 | ✅ LIVE | Main API gateway, revenue loop |
| **PPC Router** | :9200 | ✅ LIVE | 5-headed billing engine |
| **Switchboard** | :9100 | ✅ LIVE | AGI + SI routing |
| **Crawler/Leads** | — | ✅ LIVE | 78K+ leads/day |
| **Solana Listener** | — | ⚠️ DUPLICATE | 2 processes (9865, 9872) |
| **Intelligence Loop** | — | ✅ LIVE | Host-level |
| **Agents (18+)** | — | ✅ LIVE | systemd managed |

---

## 3. KEY ENDPOINTS (all on 10.118.155.218:8081)

```bash
# Health
curl http://10.118.155.218:8081/health
curl http://10.118.155.218:8081/v1/health/deep

# Revenue
curl http://10.118.155.218:8081/v1/revenue/snapshot

# Leads & Crawler
curl http://10.118.155.218:8081/v1/crawler/stats
curl http://10.118.155.218:8081/v1/leads/counts

# Buyer onboarding
curl -X POST http://10.118.155.218:8081/v1/buyers/apply \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","niche":"roofing","email":"test@v.co","tier":"silver"}'

# PPC billing
curl -X POST http://10.118.155.218:8081/v1/ppc/charge \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"test","amount_cents":1500,"charge_type":"ppl"}'
```

---

## 4. REVENUE SNAPSHOT (LIVE)

```json
{
  "total_real_revenue_usdc": 1552.5,
  "total_committed_pipeline_usdc": 81363.9,
  "outreach_opportunities": 500,
  "vault_live_usdc": 0,
  "settlements": {
    "si_charges_succeeded": 14857,
    "ppc_paid": 3,
    "ppc_open": 14242,
    "subs_awaiting_payment": 2841,
    "subs_active": 15163
  },
  "a2a": {
    "quotes_released": 4,
    "released_revenue_usdc": 1552.5
  },
  "lease": {
    "active": 4,
    "active_revenue_usdc": 880.0
  }
}
```

---

## 5. LEAD PIPELINE (LIVE)

- **Today**: 78,497 leads (62,223 general_contractor + 16,274 plumbing)
- **Tier breakdown**: A=21,481 | B=57,016
- **Expected revenue**: $5.54M
- **Strategy**: nurture=6,697 | buyer_marketplace=71,800

---

## 6. SYSTEM STARTUP (canonical)

```bash
# Full startup (run on host)
/root/empire_os/start_empire_os_full.sh

# Or manual per-component:
# 1. Hub API (in empire-hub container)
incus exec empire-hub -- systemctl start empire-hub-8081.service

# 2. Host agents
nohup /root/venv/bin/python3 -m empire_os.intelligence_loop > /root/empire_os/logs/intelligence_loop.log 2>&1 &
nohup /root/venv/bin/python3 /root/empire_os/empire_os/north_mini_agent.py > /root/empire_os/logs/north_mini_agent.log 2>&1 &

# 3. Container agents (in empire-hub)
incus exec empire-hub -- bash -c "
  nohup /root/venv/bin/python3 /root/empire_os/empire_os/lane_monitor.py > /root/empire_os/logs/lane_monitor.log 2>&1 &
  nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/lead_sniper_agent.py > /root/empire_os/logs/lead_sniper.log 2>&1 &
  nohup /root/venv/bin/python3 -m empire_os.agents.predictive_agent > /root/empire_os/logs/predictive_agent.log 2>&1 &
  nohup /root/venv/bin/python3 /root/empire_os/empire_os/agents/solana_listener_agent.py > /root/empire_os/logs/solana_listener.log 2>&1 &
"

# 4. Verify
curl http://10.118.155.218:8081/health
curl http://10.118.155.218:8081/v1/health/deep
```

---

## 7. HUB.PY ARGPARSE (NEW)

```python
# hub.py __main__ block now supports:
#   --host 0.0.0.0
#   --port 8081
#   --workers 1
# Defaults from env: EMPIRE_HOST, EMPIRE_PORT, EMPIRE_WORKERS
```

**Systemd service** (`/etc/systemd/system/empire-hub-8081.service`):
```ini
Environment=EMPIRE_PORT=8081
Environment=EMPIRE_HOST=0.0.0.0
Environment=EMPIRE_WORKERS=0
ExecStart=/root/venv/bin/python3 -m empire_os.hub
```

---

## 8. KNOWN ISSUES (to fix)

| Issue | Severity | Fix |
|-------|----------|-----|
| Solana RPC DNS resolution fails in container | Medium | Fix `/etc/resolv.conf` or use IP in Helius URL |
| Duplicate solana_listener_agent (2 PIDs) | Low | Kill one, ensure single systemd unit |
| `/v1/buyers/apply` timeout on deep health | Low | Increase timeout or fix downstream |
| `/v1/ppc/charge` timeout on deep health | Low | Same as above |

---

## 9. PRICING MODEL (5-Headed)

| Head | Rate | Target | Settlement |
|------|------|--------|------------|
| 1. Pay-Per-Call (90s) | $15/call | Roofing, plumbing, HVAC | Instant card |
| 2. Hybrid Whale | $200 + 7% | Storm, solar, mass tort | USDC on close |
| 3. Pay-Per-Lead | $45/lead (×3 max) | AEO form-fills | USDC |
| 4. Pay-Per-Schedule | $150/appt | Busy contractors | USDC |
| 5. Native PPC Arbitrage | $8/CPC | Cheap clicks → high intent | USDC |

**Subscription Tiers** (buyer-facing):
- Bronze: $200/mo, 1 lane, $15/call, $150 connect, 5% backend
- Silver: $500/mo, 5 lanes, $20/call, $200 connect, 7% backend
- Gold: $1,000/mo, 25 lanes, $25/call, $250 connect, 10% backend
- Enterprise: $9,900/mo, custom
- Whale: $50,000/mo, unlimited, negotiated

---

## 10. FILE REFERENCE

| Path | Purpose |
|------|---------|
| `/root/empire_os/empire_os/hub.py` | Main FastAPI app (8081) |
| `/root/empire_os/empire_os/ppc_router.py` | PPC billing (9200) |
| `/root/empire_os/empire_os/switchboard.py` | Call routing (9100) |
| `/root/empire_os/empire_os/revenue_engine.py` | Revenue snapshot |
| `/root/empire_os/empire_os/health_deep.py` | Deep health check |
| `/root/empire_os/start_empire_os_full.sh` | Full startup script |
| `/root/empire_os/scripts/load_secrets.py` | Vault → env loader |
| `/etc/systemd/system/empire-hub-8081.service` | Hub systemd unit |
| `/root/empire_secrets/` | Vault (mode 0700, files 0600) |

---

## 11. VERIFICATION COMMANDS

```bash
# Quick health
curl -s http://10.118.155.218:8081/health | jq
curl -s http://10.118.155.218:8081/v1/health/deep | jq

# Revenue
curl -s http://10.118.155.218:8081/v1/revenue/snapshot | jq '.kpis'

# Leads
curl -s http://10.118.155.218:8081/v1/crawler/stats | jq '.leads_posted_today, .expected_revenue_usd'

# Process check
incus exec empire-hub -- ps aux | grep -E "hub|sniper|solana|crawler|lane"
```

---

## 12. DEPLOYMENT NOTES

- **Container DB is source of truth**: `/root/empire_os/empire_os.db` (736MB, 432K lane_leads)
- **Host DB is stale**: 9.6MB, do not use
- **Secrets**: `/root/empire_secrets/` (SOLANA_PAYER_SECRET, RPC_URL, VAULT_WALLET, etc.)
- **Brevo email**: 300/day free tier, quota-aware batching in `brevo_quota.py`
- **Resend blocked**: Cloudflare 1010 from container IP

---

*End of Enhanced Startup Guide — save this file for future reference*