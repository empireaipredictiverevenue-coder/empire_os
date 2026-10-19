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

## Lead-scoring tool audit (19 October 2026)

Founder asked to reconnect **CORTEX, OMEGA, lead scoring and enrichment** across the same business section.

Exact files relative to `/srv/empire_os/`:
- `empire_os/cortex_learning_loop.py` — feedback from account-twin research, verified payment, fulfilment and outcome packets.
- `empire_os/intelligence/omega.py`, `empire_os/omega_worker.py`, `empire_os/omega_buyer_readiness.py` — Omega 2 opportunity baseline, canonical score reader/writer and buyer identity/readiness checks.
- `empire_os/omega_os.py` — legacy Omega scorer imported by `empire_os/hub.py`; **not** authoritative Omega 2 scoring evidence.
- `empire_os/lead_scoring.py`, `empire_os/lead_scoring_v2.py`, `empire_os/qualification_worker_v2.py` — canonical evidence-qualified scoring path.
- `empire_os/prospect_enrichment.py`, `empire_os/evidence_enrichment_planner.py` — first-party website/identity and evidence enrichment feeding qualification v2.
- `empire_os/enrichment.py` — legacy generic enrichment imported by hub, not the v2 canonical scoring receipt.
- `empire_os/hunter/enrichment_worker.py`, `empire_os/buyer_deferred_enrichment.py` — separate buyer and hunter enrichment pipelines.
- `empire_os/competitor_audience_omega_cortex.py` — competitor-audience research priority projection, not the same as paid-lead outcome CORTEX.
- `scripts/run_qualification_cycle.py` — scheduled orchestration of signal resolution → v2 qualification → evidence recovery → identity catchup → Omega score → Omega buyer-readiness review.
- `migrations/empiredb/009_active_schema_parity_wave1.sql` — `prospect_qualifications`.
- `migrations/empiredb/011_intelligence_schema_parity.sql` — `intelligence_scores`.

Runtime observations:
- `empire-qualification.timer` active, with successful last `empire-qualification.service` completion on 19 October 10:17 UTC. **Successful process exit does not prove any scored rows or a buyer-ready result.**
- `empire-buyer-deferred-enrichment.timer` ran 19 October 10:19 UTC; service exit success does not prove useful leads.
- `empire-enrich-rescore.timer` inactive; its units point to a legacy `/root/.hermes/scripts/` job. Do not enable alongside qualification v2 without ownership and output review.
- `runtime/cortex_learning/cortex_learning_latest.json` last generated **22 September 2026**, 2 learning packets, 0 learning-ready, 0 verified-customer learning. **Stale**; not a live trained revenue predictor.

Additional additive scoring bridge:
- `empire_os/lead_scoring_inventory_bridge.py`: model-specific read-only score inventory. It only counts Omega scores linked to the **current** v2 qualification ID and matching active entity identity. Unknown or stale scores remain separate.
- `scripts/report_niche_lead_supply_empiredb.py`: optionally reads canonical `prospect_entity_links` and `intelligence_scores`; a failed reader explicitly returns unavailable instead of faking zero. Adds CORTEX snapshot age, enrichment receipts and hot/warm/unknown coverage by niche.
- `/founder/lead-supply`: new private score-coverage and engine-directory section, without any scoring-worker dispatch.

**No live DB census has run under this feature branch:** the shell does not contain protected `EMPIREDB_DSN`; the existing qualification/exchange services use their provisioned environments. Do not copy secrets or bypass service credential boundaries.

Next release checkpoint: approve an isolated, read-only reporting service under an explicitly scoped EmpireDB reader role; validate per-niche score joins on real rows; then release private API and frontend together. CORTEX refresh and any behaviour-changing score promotion need a separate, evidence-backed decision.

## Current Phase 4 MRR / territory package linkage (19 October 2026)

The customer package architecture was previously built and must be **reused**:
- `empire_os/phase4_exchange_mrr_products.py` — current, founder-approved monthly seat catalogue:
  - `exchange_seat_starter` USD $99/mo, **1** corridor
  - `exchange_seat_growth` USD $249/mo, **5** corridors
  - `exchange_seat_pro` USD $499/mo, **25** corridors; eligible for negotiated exclusivity only
  - `exchange_seat_enterprise` USD $999/mo, **custom** corridor limit; eligible for negotiated exclusivity only.
- `empire_os/exchange_self_serve.py` — collects niche, territory, stated capacity, requested seat tier, preferred delivery, exclusivity interest **as nonbinding demand**. No capacity/contract/payment verification.
- `empire_os/founder_approved_commercial_sync.py` — existing canonical product identity/approved price sync, not guaranteed fulfilment economics.
- `migrations/empiredb/000_empiredb_canonical_base.sql` — `strike_packs` and `buyer_subscriptions` as legacy-compatible canonical records; historical Stripe fields do not prove a USDT/BSC receipt.
- `empire_os/mrr_product_recovery.py` and `empire_os/marketplace.py` — legacy Bronze/Silver/Gold/etc. are migration references only; never substitute historic price or SQLite seats for Phase 4 terms.
- `empire_os/data_brokerage_monetization_portfolio.py` — research hypotheses for derived territory-intelligence licences; **not** interchangeable with lead delivery packages or published customer agreements.

### Additive territory/MRR bridge implemented in this branch

`empire_os/lead_territory_mrr_bridge.py` projects the four existing product tiers against canonical exchange seat records and observed qualified supply, with optional separate read-only inventories of `strike_packs` and `buyer_subscriptions`.

It distinguishes:
- product catalogue fee **vs** a canonical subscription row's nominal monthly amount **vs** independently verified recurring revenue (unknown here);
- buyer seat record **vs** buyer-capacity-ready seat **vs** commercially granted customer entitlement (unverified here);
- a niche+metro market **vs** an exact delivery corridor identity **vs** a contracted territory right or exclusivity (unverified here);
- a subscription row marked active **vs** a valid receipt and accepted contract (not demonstrated by status alone).
- Buyer-delivery corridor keys often end in `webhook` or `phone`; lead-supply keys end in `lead`. Never treat these distinct corridors as an exact delivery match. The new `territory_markets` groups by normalized niche+metro for analysis only.

`scripts/report_niche_lead_supply_empiredb.py` optionally reads existing canonical `strike_packs` and `buyer_subscriptions` with bounded pages and fail-closed unknown states. This does **not** activate payments, renewals, entitlements or record recognised MRR.

`GET /v1/founder-lead-supply/packages` is a *new private founder read-only route*. It can show a Phase 4 catalogue and current exchange-market snapshot before the full DB lead census is deployed; if the census exists, it uses the counted package/subscription evidence. The frontend `/founder/lead-supply` has a separate package panel so the catalogue remains available even when the optional census has not been released.

The live canonical exchange snapshot observed 19 October 10:33:14 UTC projected four existing product tiers, 157 distinct buyer/supply corridor keys, 58 corridor keys with overflow and zero buyer-capacity-ready corridors. **Do not interpret these as 157 unique geographic territories or verified subscriptions.** The full `buyer_subscriptions` and `strike_packs` census has not yet run in the private reader role.

### Next revenue-facing work

1. Run a bounded, authorized **read-only** EmpireDB inventory census for current packs and subscriptions. Compare with buyer seat state and commercial terms; do not count legacy Stripe fields or a status flag as paid revenue.
2. Reconcile requested `requested:niche:territory` self-serve keys against canonical niche/metro, preserving jurisdiction, granularity and original request evidence. No automatic acceptance/territory reservation.
3. Confirm exactly one first paid buyer/pilot with independently verified capacity, terms and supported delivery, then expose limited, agreement-backed inventory in the tenant self-serve portal.
4. Attribute recurring membership invoices, USDT/BSC verification and actual realised MRR through the existing Revenue Truth/Metering and Economic Memory layers. Never infer from hypothetical package pricing.
5. Only after evidence, activate entitlement issuance, territory overlap arbitration, expiry/revocation, allocations and authenticated buyer self-serve views in their respective owning services.

No new payment rail, no public checkout mutation, no schema changes, no billing activation, no production service restart and no conflicting owner changes from this branch.

## 19 October 2026 — Snapshot census & release hardening (additional continuation)

### Accuracy correction
The original `prospect_qualifications` SELECT excluded `score` although canonical
`buyer_allocation.qualification_decision()` requires score >= its threshold.
This caused false unqualified counts. **Corrected:** select `score` and test
real score/evidence-tied market counts. Never publish a historical result from
the old version.

### Database snapshot consistency
The existing PostgreSQL `EmpireDbProvider.read_only_snapshot()` is reused:
`REPEATABLE READ READ ONLY`, backed by one actual database transaction.
The three *required* tables—`prospects`, `prospect_acquisitions`,
`prospect_qualifications`—share one point-in-time database snapshot.
`prospect_entity_links` + `intelligence_scores` share a **separate**
point-in-time snapshot. Optional `strike_packs` and `buyer_subscriptions`
use their own snapshots so an absent optional permission cannot abort the core
count. The separately written commercial exchange JSON is at a different
observed time. The API emits exact consistency flags and **never implies one
atomic commercial snapshot across all these sources**. The record cap,
duplicate checks and fail-closed required-table behavior remain.

### Market + qualified supply joined
`empire_os/lead_territory_supply_join.py` reconciles the counted
`niche_metro_counts` with the existing Phase 4 `territory_markets`:
- joins on canonical niche family and normalized metro only;
- includes both matched markets and source-supply-only markets with no
  exchange corridor;
- separately counts unique owned leads and score/evidence-qualified leads;
- verifies market subtotals equal the complete same-snapshot database census;
- explicitly leaves delivery-route match, sale eligibility, exclusivity,
  buyer seats and billing unverified;
- issues an actionable founder-only next step when no verified buyer capacity
  exists. This is **not** an automated sales entitlement or allocation.

### Held operational packaging
New staged files:
- `scripts/preflight_lead_supply_census_20261019.py`
- `deploy/systemd/empire-lead-supply-census.service`
- `deploy/systemd/empire-lead-supply-census.timer` (half-hourly proposal only).

**None of these services/timers have been installed.** The service requires
the main-repo source after a conflict-free release, a dedicated
`/etc/empire_lead_supply_reader.env` with only the private
`EMPIREDB_DSN`, and a writable
`/srv/empire_os/runtime/lead_supply` target. A successful staged unit
validation does not grant production release authorization.

The preflight is fail-closed and refuses:
- unrelated DB backends, non-`empiredb` databases, non-local PostgreSQL endpoints;
- login names other than `empire_lead_supply_reader_login`;
- missing required SELECT columns, stale/noncanonical exchange snapshots;
- any privileged role flags, inherited/membership rights, table/column
  write privileges on the selected tables;
- missing explicit permissive `USING(true)` SELECT RLS policies for the
  dedicated reader (or restrictive RLS policy for that role).

**Important governance blocker:** migrations
`003_prospect_acquisition_ledger.sql`,
`014_structural_hardening_parity.sql`,
`015_active_runtime_schema_parity.sql` and
`018_tenant_context_foundation.sql` enable RLS for these tables. Merely
granting SELECT to a new role could produce silently filtered zero/partial
counts. Correct founder-scoped policy and least-privileged role design
requires a *separately approved and DBA-reviewed DDL change*; no migration,
login, role grant, RLS policy, credential or DB session with private
production credentials was created by this branch.

Required selected columns before role-scoped review:

| Source table | Minimum projected columns |
|---|---|
| prospects | id, niche, metro, status |
| prospect_acquisitions | id, prospect_id, source |
| prospect_qualifications | id, prospect_id, scoring_engine, scoring_version, status, tier, score, evidence_confidence, scored_at, entity_id, result_payload |
| prospect_entity_links | id, prospect_id, entity_id, active |
| intelligence_scores | id, entity_type, entity_id, score_type, model_key, confidence, scored_at, features |
| strike_packs | id, slug, name, tier, monthly_price_cents, price_per_lead_cents, max_leads_per_month, lane_count, niches, is_active, is_public |
| buyer_subscriptions | id, buyer_id, pack_id, monthly_price_cents, active, status, period_start, period_end |

Core lead counts fail if a required source is unreadable; optional scores and
subscriptions are marked unknown rather than zero. Do not copy credentials
from existing applications or widen tenant customer roles just to bypass RLS.

When the database capability has been separately authorized and verified,
a human can run the explicit private probe using the dedicated reader
service's environment, then execute one bounded read-only census and
review the resulting non-PII founder dashboard against the canonical
Exchange. Only after that release the API/frontend with the existing founder
authentication. Public `/buy` interest-only behavior stays unchanged.

This continuation did not trigger live crawling, public publication,
outbound, billing, financial activation, RLS updates, customer entitlement
creation or a service restart.

### Further safety clarification

The collector's executable entrypoint also rejects DSNs whose database name,
host or login identity is not the dedicated local EmpireDB reader, even if the
preflight were skipped. Shared pure validation is in
`empire_os/lead_supply_read_authority.py`.

The preflight's `audit_dedicated_reader_security` additionally uses a
database-enforced READ ONLY PostgreSQL catalog transaction. It checks:
- the login has no superuser, create-role/database, replication or
  BYPASSRLS attributes;
- no direct role memberships;
- no INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES or TRIGGER table
  privileges, nor column-level writes on the seven selected sources;
- explicit permissive role-scoped RLS SELECT policies with
  `USING(true)` for all seven selected source tables, and absence of
  restrictive policies applicable to the role.

This role-wide cross-tenant *founder-only observatory* scope, especially on
`buyer_subscriptions`, requires **explicit founder authority expansion and
a DBA privacy/security review**, not implicit code approval. Service activation
remains held.

Scoped continuation verification: 157 Python tests passed; the existing
founder Next.js TypeScript project passed `tsc --noEmit`. Only one external
Starlette/anyio deprecation warning observed.

The role, RLS, service, timer, new founder endpoint and new Next.js page
have NOT been released to production in this branch.
