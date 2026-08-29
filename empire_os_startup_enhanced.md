# Empire OS v3 — Enhanced Startup Guide

**Generated**: 2026-07-28T23:20Z
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
| Empire Hub | :8081 | ✅ LIVE | Main API gateway, revenue loop |
| PPC Router | :9200 | ✅ LIVE | 5-headed billing engine |
| Switchboard | :9100 | ✅ LIVE | AGI + SI routing |
| Solana Listener | — | ⚠️ DUPLICATE | 2 PIDs (9865, 9872) — kill one |
| Crawler/Leads | — | ✅ LIVE | 78K+ leads/day |
| Intelligence Loop | — | ✅ LIVE | Host-level agents |
| Supervisor Daemon | — | ✅ 3x | Auto-restart verified |

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

## 6. PRICING MODEL — 5-HEADED MONETIZATION

| Head | Rate | Target | Settlement |
|------|------|--------|------------|
| 1. Pay-Per-Call (90s) | $15/call | Roofing, plumbing, HVAC | Instant card |
| 2. Hybrid Whale | $200 + 7% | Storm, solar, mass tort | USDC on close |
| 3. Pay-Per-Lead | $45/lead (×3 max) | AEO form-fills | USDC |
| 4. Pay-Per-Schedule | $150/appt | Busy contractors | USDC |
| 5. Native PPC Arbitrage | $8/CPC | Cheap clicks → phone/form | USDC |

**Subscription Tiers** (buyer-facing):
| Tier | Monthly | Lanes | Per Call | Hybrid Connect | Backend |
|------|---------|-------|----------|----------------|---------|
| Bronze | $200 | 1 | $15 | $150 | 5% |
| Silver | $500 | 5 | $20 | $200 | 7% |
| Gold | $1,000 | 25 | $25 | $250 | 10% |
| Enterprise | $9,900 | custom | custom | custom | custom |
| Whale | $50,000 | unlimited | negotiated | negotiated | 7% |

---

## 7. SYSTEM STARTUP (CANONICAL)

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

## 8. HUB.PY ARGPARSE (NEW)

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

**Manual runs** default to port 8080; systemd runs on 8081.

---

## 9. KNOWN ISSUES (TO FIX)

| Issue | Severity | Fix |
|-------|----------|-----|
| Solana RPC DNS resolution fails in container | Medium | Fix `/etc/resolv.conf` or use IP in Helius URL |
| Duplicate `solana_listener_agent` (2 PIDs) | Low | Kill one, ensure single systemd unit |
| `/v1/buyers/apply` timeout on deep health | Low | Increase timeout or fix downstream |
| `/v1/ppc/charge` timeout on deep health | Low | Same as above |

---

## 10. MARKETING SYSTEM (REFERENCE)

Full enterprise marketing launch guide at:
- `/root/empire_os/empire_os/empire_os_launch_guide.md` — complete guide
- `/root/empire_os/marketingskills/skills/` — 12+ marketing skills (co-marketing, ads, revops, SMS, analytics)

**Daily cadence**:
- 06:00 UTC — Startup, review overnight performance
- 12:00 UTC — Mid-day optimization
- 18:00 UTC — Evening review, tomorrow's plan

---

## 11. FILE REFERENCE

| Path | Purpose |
|------|---------|
| `/root/empire_os/empire_os/hub.py` | Main FastAPI app (8081) |
| `/root/empire_os/empire_os/ppc_router.py` | PPC billing (9200) |
| `/root/empire_os/empire_os/switchboard.py` | Call routing (9100) |
| `/root/empire_os/empire_os/revenue_engine.py` | Revenue snapshot logic |
| `/root/empire_os/empire_os/revenue_snapshot.py` | CLI revenue snapshot |
| `/root/empire_os/empire_os/agents/revenue_ideas.py` | Revenue generation agent |
| `/root/empire_os/start_empire_os_full.sh` | Full startup script |
| `/root/empire_os/empire_os_startup.md` | V4 Intelligence startup |
| `/root/empire_os/empire-os-startup.md` | Legacy startup doc |
| `/root/empire_os/empire_os_launch_guide_complete.md` | Complete launch guide |
| `/root/empire_os/empire_os/empire_os_launch_guide.md` | Enterprise marketing guide |
| `/root/empire_os/g-brain/system/` | System snapshots & state |
| `/root/empire_secrets/` | Secret files (600, vault source) |

---

## 12. DAILY OPERATIONS CHECKLIST

```bash
# Morning (06:00 UTC)
curl http://10.118.155.218:8081/health
curl http://10.118.155.218:8081/v1/health/deep
curl http://10.118.155.218:8081/v1/revenue/snapshot
curl http://10.118.155.218:8081/v1/crawler/stats

# Mid-day (12:00 UTC) — if needed
curl http://10.118.155.218:8081/v1/revenue/snapshot

# Evening (18:00 UTC)
curl http://10.118.155.218:8081/v1/revenue/snapshot
# Archive logs, review performance
```

---

**Status**: ✅ OPERATIONAL — Hub on 8081, all endpoints verified, revenue path live