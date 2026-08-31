# EMPIRE OS — Workflow Diagrams (Mermaid, copy-paste ready)

Valid Mermaid. Arrows are edges (`-->`), labels on edges (`-->|label|`). No `->` inside boxes.

---

## DIAGRAM 1: Lead Marketplace Loop (Line A — core)
```mermaid
flowchart TD
    CR[CRAWLER / SCRAPER] --> CRM[(crm_leads — 9764)]
    CRM --> OMEGA[OmegaScore 8-dim]
    OMEGA --> LANE[(lane_leads — 4666 scored)]
    LANE --> APPLY[/v1/buyers/apply/]
    APPLY --> GATE{email verify gate}
    GATE -->|junk: @v.co / probe / example| REJECT[HTTP 400 reject]
    GATE -->|real email| ONB[auto_onboard.onboard]
    ONB --> SUB[(si_subscription awaiting_payment)]
    SUB --> PAYURL[pay_url to vault 0x1339...]
    PAYURL --> FUND[USDT BSC funded]
    FUND --> ACTIVE[(si_subscription active)]
    ACTIVE --> DELIVER[(delivered_leads)]
    DELIVER --> BILL[per_lead_cents billed]
    BILL --> INV[(si_invoice)]
    INV --> SETTLE[bsc_listener settle]
    SETTLE --> VAULT[(vault 0x1339...)]
```
FIXED: email gate hardened (hub.py line 2050). Vault in hub .env.
TODO: per_lead_cents default on active subs (billing fires on delivery).

---

## DIAGRAM 2: SMB SaaS SKU Loop (Line B — 18 products)
```mermaid
flowchart TD
    LAND[landing / aeo_page] --> BUY[/v1/products/buy/]
    BUY --> INV[(si_invoice USDT BSC)]
    INV --> SETTLE[bsc_listener settle]
    SETTLE --> PROV[provision tenant]
    PROV --> EMAIL[Brevo outbox access email]
    EMAIL --> ACTIVE[product active]
```
TODO: buy to settle to deliver email loop not wired (0 sales).

---

## DIAGRAM 3: Omega AI Engine Loop (Line C — separate business)
```mermaid
flowchart TD
    O[omega_ai_learning_engine :9100] --> C[/api/trpc/aiLearning.executeFullCycle/]
    C --> R[8-area output]
    R --> T[API key tenant tier]
    T --> M[Metered calls]
    M --> MT[(omega_metering table)]
    MT --> B[Monthly settle]
    B --> VAULT[(vault 0x1339...)]
    VAULT --> OS[Empire OS hub + bsc_listener]
```
LIVE: service active :9100, real OmegaScore 8-dim, metered calls tracked, settles to vault.
NOT lane client — separate business, shares infra only.

---

## DIAGRAM 4: Mass Tort / Legal Loop (Line D — build)
```mermaid
flowchart TD
    SRC[tort_source] --> MT[(masstort_leads — NEW)]
    MT --> OMT[Omega tort-weighted score]
    OMT --> LMT[(lane_leads source=masstort)]
    LMT --> LB[legal buyers — contingency 33%]
    LB --> CASE[case settle]
    CASE --> RESID[residual revenue]
```
BUILT: masstort_leads table created this session.
TODO: tort source ingestion + legal buyer onboarding.

---

## DIAGRAM 5: 5-Phase Automation (live, recording)
```mermaid
flowchart LR
    T1[discovery.timer] --> D[run_phase discovery]
    T2[scoring.timer] --> S[run_phase scoring]
    T3[outreach.timer] --> O[run_phase outreach]
    T4[ml_loop.timer] --> M[run_phase ml_loop]
    T5[reporting.timer] --> R[run_phase reporting]
    D --> AR[(automation_runs)]
    S --> AR
    O --> AR
    M --> AR
    R --> AR
```
LIVE: 5 timers enabled, record_run writes success/failure to automation_runs.

---

## SCHEMA (key tables)
```sql
-- Line A
si_subscription(subscription_id, tenant_id, plan, seats, price_cents,
  status, per_lead_cents, webhook_url, payment_ref)
si_tenant(tenant_id, email, ...)
delivered_leads(id, lead_ref, buyer_id, lane_id, credit_cost, status, delivered_at)
si_invoice(id, amount_cents, status, ...)
si_settlements(id, amount_cents, settled_by, ...)

-- Line B
si_products(sku, name, tier1_usdc, tier2_usdc, tier3_usdc, tier4_usdc,
  setup_fee_usdc, active, ...)

-- Line C (NEW)
omega_metering(id, tenant_id, area, calls, recorded_at)

-- Line D (NEW)
masstort_leads(id, case_type, claimant_name, email, phone, state,
  status DEFAULT 'pending', omega_score, created_at, source)

-- Automation
automation_runs(id, phase, status, started_at, completed_at,
  duration_seconds, result_json, error_message)
```

---

## SERVICE STATUS (verified 2026-08-29)
| Service | Status | Port |
|---|---|---|
| empire-hub-8081 | activating | 8081 |
| empire-omega-learning | active | 9100 |
| empire-omega-os | activating | — |
| empire-bsc-listener | active | — |
| empire-supervisor | active | — |
| empire-omega-automation@ (5 timers) | enabled | — |
| empire-omega-ai | disabled (dup) | — |

Omega endpoints confirmed:
- GET /v1/health → ok
- POST /v1/omega/score → real 8-dim (tier bronze, 24.1)
- POST /api/trpc/aiLearning.executeFullCycle → metered, settles to vault

FIXES THIS SESSION:
1. Email verify gate hardened (hub.py)
2. Omega engine import fixed (OmegaScore not OmegaScoreEngine)
3. Omega metered-call settlement to vault wired
4. masstort_leads table created
5. Dup empire-omega-ai disabled (port clash)
6. Stale 9100 process killed, omega restarted
7. 5-phase automation recording verified
