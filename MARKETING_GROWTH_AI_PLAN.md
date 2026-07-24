# EMPIRE OS v3 — Marketing + Growth + AI Coordination Plan

**Author**: Hermes (MiniMax-M3) | **Date**: 2026-07-23 | **Status**: ACTIVE
**Source of truth**: `/root/g-brain/build/BLUEPRINT_POINTERS.md` (90-day plan + billion-scale thesis)

---

## 1. CURRENT STATE — what works, what's dead (live-verified)

### Live (systemd timers + pm2)
| Service | Cadence | Last run | Status |
|---|---|---|---|
| `empire-cortex-ai.timer` | 30 min | 13 min ago | **LIVE** — rule-based fallback active (LLM credits dry) |
| `empire-cortex-health.timer` | 5 min | recent | LIVE |
| `empire-content-engine.timer` | 8 h | 24 min ago | LIVE |
| `empire-seo-loop.timer` | 24 h | 22 h ago | LIVE |
| `empire-market-sweep-daily.timer` | 24 h 05:00 | 11 h ago | LIVE (17 niches × 10 metros, limit 20) |
| `empire-market-sweep-roofing.timer` | 24 h 06:30 | 9 h ago | LIVE (subsumed by daily sweep) |
| `empire-daily-briefing.timer` | 24 h 08:00 | 8 h ago | LIVE |
| `empire-marketing-deploy.timer` | 23 h | 13 min ago | LIVE |
| `empire-mass-tort-intel.timer` | 6 h | just started | LIVE (newly wired Jul 23) |

### Dead (pm2 deleted during hub restart recovery, need revival)
| Agent | Role | Reason |
|---|---|---|
| `empire-marketplace` | A2A push | killed by `pm2 delete all` |
| `empire-markets-analysis` | market intel | killed |
| `empire-business` | decision surface | killed |
| `empire-conversion` | funnel | killed |
| `empire-copywriting` | landing copy | killed |
| `empire-email` | outreach drafts | killed |
| `empire-engineering` | ticket queue | killed |
| `empire-funnel` | funnel logic | killed |
| `empire-growth` | opportunity finder | killed |
| `empire-ppc-router` | PPC marketplace | killed |
| `empire-ppl-service` | pay-per-lead engine | killed |
| `empire-lead-handler` / `empire-lead-sniper` / `empire-lead-sources` | lead pipeline | killed |
| `empire-guardian` / `empire-sentry` / `empire-supervisor` | watchdog layer | killed |
| `empire-ai-closer` | buyer closer | killed |
| `empire-ai-seo-agent` / `empire-seo-agent` | SEO | killed (systemd timer still works) |
| `empire-product-research` | research | killed |
| `empire-inbound-reply-daemon` | reply handler | killed |
| `empire-AGI` / `empireagi` | AGI loop | killed |

### Live infrastructure (recently fixed Jul 23)
- ✅ `/v1/swarm/lane-heat` — now reads lane_leads DB (4666 leads, tier breakdown)
- ✅ `/v1/evaluate/settlements` — column bug fixed, returns proper JSON
- ✅ `/v1/b2b/direct` — new endpoint, accepts b2b scraper output
- ✅ `mass_tort_intel.py` — wired through `enrich_lead()` + 6h systemd timer
- ✅ `b2b_scraper_intel.py` — wired through `enrich_lead()`, 6h ready (needs scheduler)

---

## 2. DATA TRUTH (verified via `sqlite3 empire_os.db`)

| Table | Count | Notes |
|---|---|---|
| `lane_leads` | 4,666 | seeded; 0 in last 24 h |
| `si_buyer_outreach` active | 183 | 0 priced (`payout_per_lead = 0`) |
| `si_settlements` confirmed | **0** | revenue loop dry |
| `si_ppl_leads` | 4 | all `dispatch_webhook_not_configured` (HTTPError 500) |
| `si_ppc_invoices` | 15 | all `open`, real USDC `solana:` pay_urls minted |
| `evaluation_ledger` | 7,215 | 0 settled |
| `carrier_rosters` | **0** | never ran |
| `carrier_applications` | 0 | never ran |
| `homeowner_jobs` | (check) | insurance-claim intake |

### The single biggest leak
**`payout_per_lead = 0` for all 183 active buyers.** No price = no delivery = no revenue. Path:
1. Bulk UPDATE `si_buyer_outreach.payout_per_lead` from lane heatmap + market rates ($4–15/lead by niche).
2. This unblocks `/v1/strike-pack/claim` → delivery → 5–10% buyer claim → settlement.

---

## 3. MARKETING PLAN — reach + content + lead capture

### Goal
Get AEO pages ranking, drive traffic to `/v1/strike-pack/claim` + `/v1/evaluate/claim`, capture the existing 7,215 graded leads into paying flow.

### Channels (existing infrastructure, restart first)

**A. AEO — Authority Engine Optimization (462 pages already built)**
- File: `empire_os/aeo_generator.py`, `aeo_checker.py`, `aeo_monitor.py`, `aeo_refresh.py`
- Cadence: weekly refresh (priority pages), monthly audit
- Status: `aeo_citations.json` last touched Jul 18 (5 days stale)
- **Action**: restart `aeo_monitor` via pm2 (every 6h, monitor 462 pages, alert on citation drops)

**B. Content engine**
- File: `empire_os/agents/content_engine.py`
- Cadence: `empire-content-engine.timer` every 8h
- Output: `/root/feedback/product_docs/` + `/root/feedback/rendered_lps/`
- Status: `run_content_engine.sh` ran 24 min ago
- **Action**: verify content is being indexed; push top-10 pages to AEO sitemap

**C. Outreach runner**
- File: `empire_os/agents/outreach_runner.py` + `email_agent.py`
- Function: queue outreach emails (Brevo + SendGrid already wired)
- Status: DEAD
- **Action**: restart, then wire `mass_tort_intel` enriched leads → outreach queue

**D. SEO loop**
- File: `empire_os/agents/seo_agent.py`, `ai_seo_agent.py`
- Cadence: `empire-seo-loop.timer` daily
- Output: `/root/feedback/ai_seo_log.jsonl` (47k bytes, recent)
- Status: timer active, agents dead
- **Action**: restart both agents under pm2

### Marketing cadence
| Day | Action | Owner |
|---|---|---|
| Mon | Cortex brain reads snapshot, posts biggest leak to `/root/feedback/cortex_brain.json` | cortex_ai |
| Tue | AEO monitor refreshes 50 priority pages | aeo_monitor |
| Wed | Content engine emits 1 new niche page + 5 supporting posts | content_engine |
| Thu | Outreach runner queues 100 emails from enriched leads | outreach_runner |
| Fri | SEO audit + competitor scan | ai_seo_agent |
| Sat | Marketing-deploy timer deploys top variant | marketing_deploy |
| Sun | Daily briefing + weekly synthesis | daily_briefing |

---

## 4. GROWTH PLAN — convert existing inventory into revenue

### Goal
Convert `lane_leads` + `evaluation_ledger` + `homeowner_jobs` into paying tenants using the 12-SKU pricing model.

### Plays (in order of ROI)

**Play 1 — Price the buyers** (UNBLOCKS EVERYTHING)
- File: `empire_os/si_buyer_outreach.py`
- SQL: `UPDATE si_buyer_outreach SET payout_per_lead = ? WHERE niche = ? AND payout_per_lead = 0`
- Defaults: $4 (mass tort), $8 (home services), $12 (legal/PI), $15 (medical)
- KPI: `payout_per_lead > 0` for ≥ 50 buyers within 7 days

**Play 2 — Wire dispatch webhook** (unblocks PPL)
- File: `empire_os/hub.py` → `dispatch_lead` endpoint
- Current: returns HTTPError 500, `dispatch_webhook_not_configured`
- Action: set env `DISPATCH_WEBHOOK_URL` + fix SQL constraint
- KPI: 4 stuck PPL leads dispatched within 24h

**Play 3 — Convert graded leads** (`evaluation_ledger`)
- File: `empire_os/agents/evaluation_product.py`
- Function: `/v1/evaluate/claim` (already live, but 0 calls today)
- Outreach: send pay_url email to top 100 graded leads
- KPI: ≥ 2 paying tenants within 30 days

**Play 4 — Carrier rosters → homeowner matches**
- File: `empire_os/carrier_rosters.py` (scaffolding exists, 0 rows)
- Socrata: TX TDI, FL DBPR, CA CSLB, plus carrier DRP (State Farm, Allstate, Farmers, Liberty, USAA, Nationwide, Travelers, Progressive)
- Action: rewrite with real Socrata endpoints, schedule daemon
- KPI: 100+ rostered contractors within 14 days

**Play 5 — Mass tort pipeline**
- File: `empire_os/empire_os/agents/mass_tort_intel.py` (just deployed Jul 23)
- Already running every 6h; reddit/courtlistener signals pending (auth fix needed)
- Outreach: high-tier enriched leads → queue for legal-firm partner outreach
- KPI: 50 court-docket signals within 7 days

### Growth cadence
- Daily: `growth_agent` (opportunity finder) — restart under pm2
- Daily: `markets-analysis` (market intel) — restart under pm2
- Hourly: `cortex_brain.json` → identify biggest leak → chief_of_stask action
- 4× daily: `outreach_runner` queue drain

---

## 5. AI COORDINATION PLAN — single source of truth for the swarm

### Goal
One cron that:
1. Reads `cortex_brain.json` (largest snapshot of state)
2. Reads `agi_decisions.jsonl` (last 7 days)
3. Reads `chief_of_staff.jsonl` (last 7 days)
4. Reads `cortex_health_watchdog.log` (last 50 lines)
5. Synthesizes 1 prioritized daily action list
6. Writes to `/root/feedback/ai_coordinator.json`
7. Telegrams Philipp the top 3

### File
**New**: `/root/empire_os/empire_os/agents/ai_coordinator.py`
**Timer**: `empire-ai-coordinator.timer` every 6h (aligned with mass-tort cycle)

### Output shape
```json
{
  "ts": "2026-07-23T16:00:00Z",
  "cortex_snapshot": {"leads": 4666, "buyers_priced": 0, "settled": 0},
  "top_leak": "183 active buyers, 0 priced → bulk UPDATE payout_per_lead",
  "top_3_actions": [
    "Price 50 buyers with default $4-15/lead rates",
    "Wire dispatch webhook (unblocks 4 stuck PPL leads)",
    "Schedule b2b_scraper_intel (new scraper ready, no timer)"
  ],
  "agent_health": {"cortex": "ok", "b2b_scraper": "needs scheduler",
                   "mass_tort": "ok", "carriers": "dead"},
  "dead_count": 18,
  "next_review": "2026-07-24T16:00:00Z"
}
```

### Wiring (Jul 23)
1. Create `ai_coordinator.py` (read 4 sources, synth, write, telegram)
2. Create systemd service + timer
3. Verify cycle end-to-end

---

## 6. EXECUTION SEQUENCE (this turn)

**Step 1** — Revive dead agents (pm2 restart with logs)
- `pm2 start` 18 agents with health checks
- Wire orchestrator back via `pm2 startup` + systemd
- Add `empire-b2b-scraper-intel.timer` (every 6h)

**Step 2** — Fix `payout_per_lead = 0` blocker
- Run bulk UPDATE with niche defaults
- Verify on `/v1/buyers/status`

**Step 3** — Wire dispatch webhook
- Set env, fix SQL
- Replay 4 stuck PPL leads

**Step 4** — Build AI coordinator
- New script + systemd timer
- Wire to Telegram (channel: Phillip)

**Step 5** — Schedule carrier rosters
- Rewrite contractor_scraper with real Socrata URLs
- Schedule `empire-carrier-roster.timer` (daily)

---

## 7. SUCCESS METRICS (90-day)

| KPI | Today | 30-day | 90-day |
|---|---|---|---|
| buyers priced | 0/183 | 50 | 183 |
| settlements confirmed | 0 | 1 | 50 |
| AEO citations | stale | 10 | 100 |
| content pages indexed | 462 | 500 | 800 |
| outreach emails sent/wk | 0 | 200 | 1000 |
| paying tenants | 0 | 2 | 10 |
| MRR | $0 | $500 | $5,000 |

---

## 8. RISKS

1. **LLM credits dry**: rule-based fallback covers cortex brain; if we need LLM reasoning in growth/copy/email agents, must fix `MINIMAX_API_KEY` env (per memory).
2. **Orchestrator resurrection loop**: PM2 keeps respawning `orchestrator.py`; if we re-enable 18 agents, monitor for the same death-loop pattern.
3. **Settlement listener**: 15 open PPC invoices never flipped to paid → solana listener not catching inbound. Separate task.

---

*Plan committed to BLUEPRINT_POINTERS as Empire OS Marketing + Growth + AI Coordination. Updates logged in `/root/feedback/plan_history.jsonl`.*
