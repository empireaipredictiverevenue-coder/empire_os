# EmpireOS Founder Checkpoint — 2026-09-20

## Canonical production state
- Repo: /srv/empire_os
- Branch: feature/revenue-intelligence-v2
- Canonical DB: Supabase owbeinlfcfdtwcwrttjy
- Payment rail: USDT on BSC
- Execution: governed; no synthetic production data; unknown remains unknown
- Protected: /srv/empire_os/recovery/ and /srv/empire_os/toop
- Git rule: explicit paths only; never git add .

## Current architecture
EmpireOS is an intelligence and revenue operating system. Scrapers/snipers are sensors, not the product.
Commercial intelligence is organized into nodes feeding a shared Intelligence Fabric.

## Intelligence Nodes
Home Services, Property Opportunity, Market Intent, Corporate Change,
Government Spend, Healthcare Growth, Compliance & Risk, Legal & Mass Tort.

## Acquisition
Adaptive diversified acquisition policy committed in 2265520.
Families: coverage, intent, property/regulatory, event/disaster.
Registered real keyless sources include overpass, biz_search, reddit, permits,
chicago_311, courtlistener, nyc_hpd and nws_alerts.

## Legal / Mass Tort recovery
- Node restored in commit b6c4e73.
- Existing assets: firm_finder, firm_import, firm_sources manifest, mass_tort_agent,
  CA/TX bar source definitions, CourtListener, Reddit mass-tort intelligence,
  Search Fabric, adgen scanner, legal AEO pages and Mass Tort Intake campaign code.
- Identity reconciliation runtime contains 547 legal candidate rows across
  522 unique firm names: 122 mass tort, 213 personal injury, 78 class action,
  73 medical malpractice and 61 workers comp.
- These 547 are candidate/dry-run intelligence, not automatically canonical live prospects.
- Next legal step: reconcile/promote only verified canonical firms into the live Intelligence Fabric.

## Current live operating constraints
- Email outbound daily cap remains 10 unless founder explicitly expands it.
- Phone/Vonage deferred for later; no live-call authority.
- Internal crawl, enrichment, qualification, intelligence and proposal work may continue automatically.
- No revenue is declared without verified payment/revenue evidence.

## Current commercial bottleneck
Raw business supply is healthy. Decision-maker identity/contact recovery remains important.
Deferred unresolved buyers stay eligible for repeated first-party enrichment rather than being failed.

## Parallel build lanes
1. Legal/Mass Tort canonical recovery: map legacy/runtime firm candidates to canonical entities without inventing or overwriting evidence.
2. Founder Console: surface intelligence nodes, source health, data products and opportunity counts without touching live authority controls.
3. Data Products/API: define node product contracts and read-only export surfaces for sellable intelligence products.

## Recent commits
- 2265520 feat(acquisition): diversify source families adaptively
- 7b8cc3f feat(intelligence): define commercial intelligence nodes
- b6c4e73 feat(intelligence): restore legal mass tort node

## Founder directive
Move fast. Do not stop for reversible engineering decisions.
Do not duplicate existing systems. Preserve concurrent work.
Only stop at genuine founder gates: destructive/irreversible changes, fund movement,
legally binding acceptance, irreversible accounting/revenue recognition, or authority expansion.
