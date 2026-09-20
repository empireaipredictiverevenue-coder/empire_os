# Empire AI / EmpireOS — Founder Console Operating Spec

Date: 2026-09-20
Status: CANONICAL PRODUCT / OPERATING SPEC

## Purpose

The Founder Console is the top-level truth surface for operating EmpireOS.

It must answer immediately:
1. Where are we making money?
2. Where could we make more?
3. What is stopping us?
4. What should happen next?

Specialist dashboards are drill-downs, not competing truth systems.

## Top-level sections

### Empire Overview
Recognized revenue, realized GP, active opportunities, current commercial blocker, owned inventory, qualified inventory, verified buyer capacity, replies/conversations, source health, active markets, Astra priority, Blueprint phase/state, mode and authority.

### Revenue Pipeline / Commercial Loop
REAL DATA → QUALIFY → OMEGA → BUYER → OUTBOUND → CONVERSATION → TERMS → CAPACITY → ALLOCATION → BSC PAYMENT REQUEST → VERIFIED USDT PAYMENT → FULFILMENT → OUTCOME → RECOGNIZED REVENUE → REALIZED GP → LEARNING

Every stage shows observed / blocked / unknown / stale plus evidence reference.

### Growth & Opportunities
Opportunity Foundry board:
DISCOVER → QUALIFY → VALIDATE → EXPERIMENT → PROVE → SCALE → DEFEND → HARVEST/RETIRE

Each card should show geography, niche/product, opportunity type, demand, supply, buyer capacity, competition, price evidence, forecast revenue/GP, actual recognized revenue/GP, experiment cost, confidence, moat value, blocker, Astra priority and next action.

### Global Markets
WORLD → COUNTRY → REGION → METRO → NICHE / PRODUCT

Show market-entry state, Jurisdiction Pack readiness, buyer network, source coverage, Search/AEO/GEO signals, demand, pricing, revenue/GP, experiments and blockers.

### Acquisition & Hunter
Current source health, latest run separately from current health, candidates, accepted/rejected quality, canonical writes, enrichment, identity/contact confidence, source/metro/niche performance, failures and eventual source-to-GP attribution.

### Buyer / GTM / Closer
Buyer candidates, outreach-ready, approved, sent/delivered/bounced/replied, conversations, closer cases, commercial terms, territory, capacity, payment reliability, retention/expansion and next justified action.

### Money / Revenue Truth
Proposed price, agreed price, payment requests, verified payments, delivered orders, recognized revenue, observed cost, realized GP and gross margin. Never collapse these states.

### Astra Command Board
Ranked workstreams, blockers, owners, intelligence route, expected value, premium AI cost/budget/ROI hurdle, rationale, evidence freshness, approval requirement and execution authority.

### Blueprint Control Room
Show phases as finished engineering, production proof pending, current, parallel build, gated or retired, plus closure requirements from the Founder Closure Ledger.

### Growth Command
Search/SEO/AEO/GEO, Advertising, Demand Genesis, landing/content performance, partnerships/distribution, experiments, Conversion Intelligence/CRO and attributed recognized revenue/GP. Conversion shows every canonical boundary from visitor→lead through outcome→repeat purchase, evidence-backed rate/drop-off, sample size, UNKNOWN/stale states, primary bottleneck and next proposal-only experiment.

### Intelligence / Learning
Omega, Predictive, forecast-vs-actual calibration, Revenue OS, Digital Twin, Capital, Economic Memory and model-review feedback.

### System / Operations
Services/timers, Supabase/API health, sources, Resend, Hunter, Search, Astra, model/provider health, errors, remediation and current OBSERVE/authority state.

## Truth presentation rules

- UNKNOWN is not 0.
- FORECAST is not ACTUAL.
- SCENARIO is not FORECAST.
- PAYMENT REQUEST is not payment.
- VERIFIED PAYMENT is not automatically recognized revenue.
- RECOGNIZED REVENUE requires Revenue Truth evidence.
- REALIZED GP requires recognized revenue and observed cost.
- Historical snapshot state is visibly distinct from current health.
- Stale evidence is visibly stale.
- Meaningful numbers are traceable to provenance.
- Dashboards may recommend; they do not silently mutate.

## Safe control layer

Later bounded controls may refresh snapshots, rerun qualification/Omega, re-enrich a bounded contact, create drafts or launch preview/verification work.

Funds, binding terms, destructive infrastructure, accounting recognition, irreversible state and authority expansion remain proper gates.

## Product structure

Founder Console is the top-level cockpit.

Search Command Centre, Revenue Command Centre, Market Intelligence, Buyer/CRM/Closer, Advertising/Demand/Experiments, Conversion Intelligence/CRO, Predictive/Capital and System Operations become drill-downs.

Avoid disconnected apps with conflicting metrics.

## Implementation order

1. Read-only Founder Overview.
2. Commercial Loop visual pipeline.
3. Astra priority board.
4. Acquisition/source health.
5. Blueprint Control Room.
6. Search/Revenue drill-down links.
7. Opportunity Foundry board.
8. Global Markets/map.
9. Buyer/GTM/Closer.
10. Money/Revenue Truth.
11. Intelligence/Learning.
12. Safe bounded controls.

## Anti-drift requirement

Any major backend capability should receive a visible read surface soon after implementation unless a documented reason prevents exposure.

The console reflects canonical evidence contracts; it is never a second database or source of truth.
