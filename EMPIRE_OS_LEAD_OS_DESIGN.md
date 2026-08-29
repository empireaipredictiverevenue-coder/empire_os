# Empire LeadOS — Apollo + Hunter + Clay clone, but better

## Positioning
One engine that does what Apollo (B2B DB + outreach), Hunter (email find/verify),
Clay (waterfall enrichment + orchestration) do separately — fused with our
proprietary Omega 8-dim scoring + our own SERP (serper) + 15-source free waterfall.

We beat them on:
1. Zero per-seat SaaS tax — we own the stack (serper key, waterfall, Omega).
2. Omega 8-dim lead quality (BRONZE→PLATINUM) vs Apollo's flat "fit score".
3. Native revenue loop — scored leads drop straight into the BSC USDT pay rail.
4. Self-learning — scoring retrains on real convert/payout data (self_learning dim).

## Architecture (modules under empire_os/)

### 1. lead_engine/  (the "Apollo" — discovery + DB)
- serp_discovery.py   — wraps /v1/web/search (serper, Google). Queries by
  niche+metro+intent ("roofing contractor Denver hiring"). → crm_leads.
- Replaces scanner.py DuckDuckGo-only path. Serper = Google coverage, no scraping bans.
- Sources: serper (primary), ddg/bing fallback, permit_signals (NYC/CHI permits),
  hiring_signals (job posts = growth intent), news_signals (M&A/expansion).

### 2. enrich_engine/  (the "Clay" — waterfall + orchestration)
- Reuse empire_enricher_pulled.py FREE_SOURCES (15) + PAID_SOURCES.
- enrich_graph.py — Clay-style visual-ish pipeline: lead → runs sources in
  priority order → fills email/phone/social/tech_stack/firmographics.
- waterfall priority: website_scraper → serper → ddg/bing → hunter(paid) →
  clearbit → apollo → pdl. Stops when email found (cost-aware).
- ADD: email_verify.py — MX + SMTP handshake (we own infra, no ZeroBounce fee).

### 3. verify_engine/  (the "Hunter" — find + verify)
- find.py   — pattern guess (info@/sales@) + serper "email" queries + hunter(paid).
- verify.py — MX lookup + SMTP RCPT TO probe + disposable/typo detection.
- Output: deliverable (valid) vs risky vs invalid. Feeds crm_leads.valid_email.

### 4. score_engine/  (our moat — Omega)
- omega_scoring.py (exists) → 8 dims → tier. Gate: only SILVER+ enters outbox.

### 5. outreach_engine/  (the "Apollo sequencer")
- enterprise_campaigns.py extended → real send via si_outbox (fix rate first).
- Sequences: 7-day outbound, weekly leadgen, reactivation.

### 6. api/  (Clay/Apollo-style API + UI)
- /v1/lead/search   — serper discovery → returns scored leads
- /v1/lead/enrich   — run waterfall on lead_id
- /v1/lead/verify   — verify email
- /v1/lead/score    — Omega score
- /products/lead_os — showcases the clone

## MVP build order (this session)
1. email_verify.py (MX + SMTP) — unblocks deliverable inventory (B task).
2. serp_discovery.py — serper→crm_leads, replaces DDG scanner.
3. Wire into enterprise_campaigns to actually produce leads (C task / 100/mo).
4. Bump mail_sender rate (A task) to drain 935 pending.
5. /v1/lead/* endpoints on hub.

## Differentiators vs competitors (one line each)
- Apollo: we score with Omega + route to USDT pay, not just "export CSV".
- Hunter: we verify via owned MX/SMTP, no $0.50/verify fee.
- Clay: our waterfall is free-first (15 sources) + serper, not $0.01/credit.

## Revenue attach
LeadOS = new product tier in si_products:
- LeadOS Starter $497/mo (5K leads/mo, serper included)
- LeadOS Growth $1247/mo (25K, waterfall + verify)
- LeadOS Scale  $2497/mo (unlimited, Omega PLATINUM routing)
Sell to the 607 buyers we already have.
