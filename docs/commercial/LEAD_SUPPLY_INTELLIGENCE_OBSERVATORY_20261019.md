# Empire AI — Lead Supply & Demand Intelligence Centre
**Founder-only, OBSERVE · 19 October 2026 · feature/lead-supply-intelligence-20261019**

## Production truth and purpose

Do not rebuild the crawler, lead scoring, buyer network, CRM, Predictive Cloud or checkout.
Canonical database: **EmpireDB PostgreSQL**, not the retired Supabase backend.
The existing `runtime/commercial_exchange/latest.json` is a **bounded, qualified selection**, not a count of all discovered leads.

Observed existing snapshot at 2026-10-19T09:52:53Z:
- selected v2-qualified prospects: **176**; identity-ready: **91**
- sampled inventory: 85 evidence-blocked, 91 no-capacity overflow, 0 allocation-ready
- buyer-seat records: **1,057**; **0 active-capacity**
- corridor keys: **157**; lane keys **33**
- verified per-lead market prices: **0**
- all 1,057 seat records blocked: 874 inactive, 156 not commercially activated, 27 test-identity holds
- no verified revenue or active delivery authority

This does **not** state the total number of lead/prospect records held in EmpireDB.
Historical `runtime/feedback/crawler_runs.jsonl` includes crawler events, duplicates and errors. Do not count its `prospect_acquired` lines as unique leads.

## Actual intelligence implementation vs proposed connection

| Layer | Existing implementation | Present relationship | What remains |
|---|---|---|---|
| Source Intelligence | `source_intelligence.py`, 22 source contracts with territory/licence/allowed-use metadata | Sourcing plan and registry; **not proof of live crawler connection** | Per-source operational heartbeat; rights for resale vs internal use |
| Crawler adapters | `lead_sources/`, `crawler_runner.py`, `crawler_data_repository.py` | Ingest candidates via canonical data gateway / acquisition ledger | Per-source unique-write, duplicate, error and freshness metrics |
| Demand-first planner | `demand_first_crawl_planner.py` | Produces bounded, reviewable proposed source runs (up to 25 candidates) | Connect verified buyer demand evidence to prioritised acquisition |
| Niche normalisation | `niche_taxonomy.py` | Used by exchange builder and new observatory | Canonical versioned taxonomy, aliases and sub-niches |
| Identity Intelligence | `prospect_identity_claims`, `prospect_entity_links`, `business_entities` | Dedup/identity evidence | Identity-resolution coverage and conflict dashboard |
| Lead Scoring v2 | `lead_scoring_v2.py`, `prospect_qualifications` | Existing qualified selection for exchange | Whole-universe score/tier/freshness counts, not just top 200 |
| Buyer Acquisition / CRM | `buyer_acquisition_scout.py`, `buyers`, CRM pilot | Buyer discovery and commercial-authority records | Evidence-backed payable capacity and faster reply triage |
| Buyer Allocation | `buyer_allocation.py`, `buyer_capacity_readiness.py` | Requires qualification, identity, activation and delivery evidence | Corridor utilisation/readiness by market |
| Exchange | `commercial_exchange_inventory.py`, `refresh_commercial_exchange.py` | Qualified sample → inventory, corridors, seats | Full-supply separate counts, unbound seat vs active capacity |
| Self-serve | `exchange_self_serve.py`, `self_serve_checkout_api.py` | Catalogue / nonbinding interest and gated checkout | Tenant entitlement, actual capacity reservation, independent payment+delivery proof |
| Predictive Cloud | `predictive_cloud_*.py` | Engine exists; **lead-level live data edge not verified** | Feed aggregate niche demand/supply forecasts with provenance, uncertainty and calibration |
| Predictive Intelligence | `predictive_intelligence.py`, `buyer_demand_graph.py` | Modules exist; **observed live use in this lead report not proven** | Demand elasticity, likelihood, buyer match and response-time signals |
| Market Sweep / Revenue GPS | `market_sweep_revenue_gps.py` | Market signal materializer exists | Join niches/metros to observed gap and economics, keep confidence separate from sales |
| Search Intelligence / SEO/AEO/GEO | `search_intelligence/` | Own search department exists; **lead-supply row join unverified** | Organic keyword gaps → owned landing pages → consented enquiry attribution |
| Permit / Property verticals | `permit_intelligence_runtime.py`, `vertical_intelligence_runtime.py` | Founder read surfaces exist | Only join licence-compliant official signals with verified entity/geography |
| Economic Memory | `economic_memory.py` | Economic-memory engine exists; lead supply link unverified | Closed-loop paid/delivered outcomes for source ROI, not forecast revenue |
| Scientific / Ling / OpenManus | Existing research/orchestration projects | No verified live lead-supply link in inspected module paths | Optional bounded enrichment/scoring workers after source & identity gates; never overwrite core truth |

**Do not label a connected Python import or a source marked 'real' as a healthy production data connection.** Health needs recent successful source run, licensing, canonical receipt, and observed lead ID.

## New isolated build in this branch

- `empire_os/lead_supply_intelligence.py`: pure niche/source/metro aggregation, active-seat vs seat-record separation, source contracts and provenance overlap, crawler event semantics.
- `scripts/report_niche_lead_supply_empiredb.py`: bounded, read-only EmpireDB canonical page scan, with count comparisons and an explicit no-transactional-snapshot qualifier; does not silently truncate.
- `empire_os/founder_lead_supply_api.py`: private founder endpoint `GET /v1/founder-lead-supply/overview`, fails closed when report unavailable.
- Founder UI `/founder/lead-supply`: niche counts, source gaps, qualified scores, seat readiness, corridor info, crawler receipts, intelligence-edge status. Not public.
- Automated tests covering deduplication, unknowns, overlapping provenance, fail-closed partial reads and private route.

**Implementation != deployment**: new worktree is not released, service restarted, or granted data/financial authority.

## Steps to achieve complete enterprise-level visibility

1. **P0 supply census:** run collector in the existing read-only EmpireDB credentials envelope, compare `prospects`, `prospect_acquisitions` and `prospect_qualifications`. Upgrade collector to a single repeatable-read transaction for a fully consistent timestamp when justified. Handle >50k rows with bounded aggregates instead of unbounded pulls.
2. **P0 pipeline quality:** distinguish raw source candidates, unique prospect identities, licensed usable records, qualified, verified identity, buyer eligible, offered, delivered, paid and realised revenue. Never double count.
3. **P0 demand truth:** no more "buyer seat" implied by a buyer row. Record commercial activation, verified cap, territory, vertical, delivery route, time window and expiry. Show blockers.
4. **P1 corridor heatmap:** niche/sub-niche × jurisdiction/metro × demand type × deliverable route. Demand availability, first-party supply, overflow, coverage, capacity and supported price evidence at identical geographic grain.
5. **P1 intelligence stitching:** entity- and time-keyed **evidence joins** from source, search, permit, property, Market Sweep, Buyer Demand Graph, Predictive Cloud and Economics; no arbitrary score-based activation.
6. **P1 founder acquisition controls:** recommended next niches sorted by *observed* buyer demand, available evidence source, quality, capacity gap and refresh costs. Review → explicit bounded dispatch, not open-loop crawling.
7. **P2 tenant self-serve portal:** verified account and tenant, jurisdiction & vertical scope, proof-based lead availability, seat request / permitted capacity, contract review, USDT/BSC settlement receipt, deduped fulfilment, SLA, invoices/usage, support/disputes and revocation. Build private preview first; activate only on separate approval.
8. **P2 closed-loop learning:** compare paid fulfilled leads to source, corridor, conversion and net realised margin in Economic Memory; track confidence and never treat expected revenue as cash.

## Gates

- £0 spend; no external paid data acquisition, uncontrolled crawling or outbound.
- No production database writes/DDL or service restarts by this branch.
- Do not expose PII or bulk raw third-party directory records through self-serve.
- Do not infer user consent, lead resale rights, pricing, territory or commitments.
- Do not introduce Supabase, legacy `seat_corridors.py` SQLite or Stripe dependencies.
- Service activation, payment, delivery, website publication, public self-serve and tenant authority require independent release gates.
