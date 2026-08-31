# EMPIRE OS — BILLION-SCALE PLAN v2 (grounded rewrite)
Generated 2026-08-29. Replaces v1 (which counted 498 test-email subs as $318K MRR pipeline).

## 0. REAL STATE (evidence from empire_os.db)
- Active subs: 65 nominal / **1 real-email** active (lane_silver, $25/mo seat)
- Awaiting: 498, **488 junk emails (98%)** → not revenue, dead weight
- Delivered leads: 4,666 (buyer_sco 1080, buyer_001 548, buyer_000 541...)
- Lane leads scored (Omega 8-dim): 4,666
- CRM total: 9,764 | Omega prospects: 4,716
- Products for sale (si_products active): **18 SKUs**, 0 sales
- Omega AI Learning Engine: service INACTIVE (8-area FastAPI exists, not running)
- Mass-tort / permit / legal lead tables: **ABSENT** (skill exists, DB not built)
- Collected lifetime: **$500.02** (1 BSC test settle $500 + 2 micro)
- 5-phase automation: live, 3 runs logged, recording works

**Verdict:** Infrastructure real. Revenue meta is fantasy. Fix collector quality + light real products before scaling.

---

## 1. PRODUCT / SERVICE CATALOG (what actually exists to sell)

### Line A — Lead Marketplace (core, live)
- Buyer seats: bronze $2.99/mo · silver $5.99 · gold $11.99 · platinum $23.99 (seat)
- Per-lead PPL: bronze $25 · silver $49 · gold $99 · platinum $199
- Inventory: 4,666 scored lane leads + 9,764 CRM + 4,716 omega prospects
- Gap: active subs have per_lead_cents=0 → billing never fires on delivery

### Line B — SMB SaaS SKUs (18 products, 0 sold)
| SKU | Floor/mo | Ceiling/mo |
|---|---|---|
| aeo_monitor T1-T4 | $29 | $999 |
| empire_leads_engine | $199 | $1,990 |
| hermes_framework | $149 | $1,490 |
| opencut_studio | $99 | $990 |
| empire_templates | $59 | $590 |
| marketingskills | $39 | $390 |
| agent_copilot | $99 | $990 |
| synthetic_agent | $199 | $1,990 |
| satellite_idle_watch | $99 | $990 |
| skillspector_audit | $79 | $790 |
| aeo_page (once) | $99 setup | $2,999 |
| ico_capital_raise | $2,999 | $9,999 setup |
| leadflow_t1-t4 | $497 | $4,997 setup |
| v4_enterprise_intelligence | $4,997 setup | — |
All 18 at 1 sub each mid-tier = **~$19K/mo ceiling per 18-direct**. Not billion alone.

### Line C — Omega AI Learning Engine (separate business, NOT lane client)
- 8-area FastAPI (:9100), 4,716 prospects scored
- Service down. Restart + monetize as API tier ($499-$4,997/mo per area-pack)

### Line D — Mass Tort / Legal / Permit (skill built, DB absent)
- v1 plan assumed 1,749 NYC permit + 16 buyers. **Tables not in DB.** Build before counting.

### Line E — Evaluation Product (8-agent, settlements=0)
- Product defined, 0 revenue. Needs paid SKU auto-deliver.

---

## 2. WORKFLOW SCHEMAS (per revenue line)

### A. Lead Marketplace loop
```
crawler/scraper → crm_leads → omega_score (8-dim) → lane_leads
→ buyer applies (/v1/buyers/apply) → auto_onboard → si_subscription(awaiting)
→ REAL email verify → pay_url (BSC vault 0x1339...) → fund → status=active
→ lead delivered → delivered_leads → per_lead_cents BILL → si_invoice → BSC settle
```
BROKEN AT: email verify (98% junk), per_lead_cents=0, vault not in hub .env.

### B. SMB SaaS SKU loop
```
landing/aeo_page → /v1/products/buy → si_invoice (USDT BSC) → settle
→ provision tenant + send access email (Brevo outbox) → active
```
BROKEN AT: 0 buy flow wired to settlement + delivery email.

### C. Omega AI loop
```
omega_ai_learning_engine (:9100) → /executeFullCycle → area outputs
→ API key tier (tenant) → metered calls → monthly settle
```
BROKEN AT: service inactive.

### D. Mass Tort loop (build)
```
tort_source → crm_leads(source='masstort') → omega_tort_weight → lane_leads
→ legal buyers (contingency 33%) → case settle → residual
```

### E. 5-Phase Automation (live)
```
discovery → scoring → outreach(email) → ml_loop → reporting
  (timers per PHASE_SCHEDULE, records to automation_runs)
```

---

## 3. PREDICTIVE MODEL (inputs = real capacity)

Capacity constants:
- Scored leads available: 4,666 lane + 4,716 omega = **9,382**
- Real active buyers today: **1**
- Real email capture rate from apply: ~2% (488/500 junk)
- PPL blended: $49 (silver median)
- Product mid-tier blended: ~$1,060/SKU/mo
- Omega engine if restarted: 4,716 prospects × $X tier

Conversion scenarios (applied to REAL buyers, not 498 ghosts):
```
real_active = 1
real_email_capture = 0.02   # fixable to 0.30 with verify gate
buyer_LTV_months = 12
```

Predicted monthly from Line A (if email gate fixed, 30/day real applies):
- 30 real applies/day × 30 = 900/mo top, convert 30% = 270 paid buyers
- 270 × $25 seat + 270 × 35 leads × $49 = $6,750 + $463K = **~$470K/mo** at scale
- Conservative (10% conv, 10/day): 90 buyers × ($25+$1,715) = **~$157K/mo**

Predicted from Line B (18 SKUs, 50 direct/mo at mid):
- 50 × $1,060 = **$53K/mo**

Predicted from Line C (Omega, 20 tenants × $999):
- **$20K/mo**

Predicted from Line D (mass tort, build first): 0 until tables exist.

---

## 4. FORECAST REVENUE (grounded, 90-day + 5-yr)

### 90-day (fix collectors + light products)
| Source | Conservative | Base | Aggressive |
|---|---|---|---|
| Line A real buyers | $157K/mo | $310K/mo | $470K/mo |
| Line B products | $8K/mo | $25K/mo | $53K/mo |
| Line C omega | $0 (restart wk2) | $10K/mo | $20K/mo |
| **Total/mo** | **$165K** | **$345K** | **$543K** |
| **Annualized** | **$1.98M** | **$4.14M** | **$6.5M** |

Assumption: email verify gate live by day 14, vault in hub .env, per_lead_cents set.

### 5-Year billion path (requires ALL lines + mass tort + enterprise)
| Year | Line A | B | C | D(tort) | Enterprise | Total/mo | Valuation(5x) |
|---|---|---|---|---|---|---|---|
| 1 | $310K | $25K | $10K | $0 | $200K | $545K | $33M |
| 2 | $1.2M | $80K | $50K | $300K | $1.5M | $3.1M | $187M |
| 3 | $3M | $200K | $120K | $1M | $5M | $9.3M | $558M |
| 4 | $5M | $400K | $250K | $2.5M | $11M | $19.1M | $955M |
| 5 | $7.7M | $774K | $400K | $3M | $11M | $22.9M | **$1.15B** |

Billion needs Year-5 ~$20M/mo recurring. Achievable ONLY if:
1. Email verify gate kills 98% junk (day 14)
2. per_lead_cents billing live (day 7)
3. Omega engine restarted (day 2)
4. Mass-tort DB built + 16 legal buyers onboarded (month 2)
5. Enterprise tier (white-label) 300 clients by Y5

---

## 5. NEXT ACTIONS (priority order)
1. **Hub .env**: add `BSC_WALLET_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8` (fixes pay_url mint)
2. **Email verify gate** on /v1/buyers/apply (reject @v.co / probe- / roofing-)
3. **per_lead_cents** default set on active subs (billing fires on delivery)
4. **Restart Omega engine**: `systemctl start empire-omega-learning` (or create unit)
5. **Mass-tort tables** build (crm_leads source='masstort' + lane_leads)
6. **Product buy→settle→deliver** email loop for 18 SKUs
7. Re-run revenue_plan.py after fixes → real MRR shows

No rewrite. Infrastructure solid. Revenue meta was fiction — now grounded.
