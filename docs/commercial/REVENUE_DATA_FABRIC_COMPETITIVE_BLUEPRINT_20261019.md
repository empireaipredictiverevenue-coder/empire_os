# Empire AI — Revenue Data Fabric: Competitive Research & Build Blueprint
**19 October 2026 | Founder continuation | isolated feature branch**
**Branch:** `feature/scrapling-revenue-data-fabric-20261019`
**Canonical database:** EmpireDB PostgreSQL. Never Supabase, never legacy SQLite.
**Default execution:** OBSERVE. No new network crawl, sender activation, billing, CRM mutation, revenue recognition or customer exposure.

## Executive decision
Do NOT build a second crawler platform. Make the existing `lead_sources` → `crawler_runner` → canonical prospect ingest → v2 qualification → Omega/CORTEX → buyer exchange → CRM/self-serve path evidence-driven. Prioritise narrow, profitable niches and verified buyer capacity. Build defensible outcomes and trust, not a vanity total of scraped rows.

## Ground-truth audit at this starting checkpoint
- Existing `empire_os/lead_sources/` contains permits, Overpass, UK solar, Reddit, 311, storms, court and business search sources. `crawler_runner.py` already has an atomic canonical ingest boundary.
- `empire_os/site_crawler.py` performs basic website contact-page extraction; `empire_os/waterfall.py` already uses it in an enrichment provider.
- `empire_os/source_intelligence.py` has licence/territory/use policies. `empire_os/demand_first_crawl_planner.py` supports bounded proposal-only plans (25 candidates).
- `empire_os/lead_supply_intelligence.py`, `lead_scoring_inventory_bridge.py`, `founder_lead_supply_api.py` and the private lead-supply UI are owned by adjacent feature branch `feature/lead-supply-intelligence-20261019`; this new branch was created from its commit 3b986a49. No deployment proven.
- Existing linked intelligence modules include `lead_scoring_v2.py`, `qualification_worker_v2.py`, `prospect_enrichment.py`, `evidence_enrichment_planner.py`, `intelligence/omega.py`, `omega_worker.py`, `cortex_learning_loop.py`, `buyer_demand_graph.py`, `market_sweep_revenue_gps.py`, `predictive_intelligence.py`, `economic_memory.py` and Search Intelligence.
- Existing observed bounded commercial exchange (not total database census): 176 v2-qualified selected, 91 identity-ready, 0 allocation-ready, 1,057 buyer-seat **records** and 0 active capacity. No verified per-lead prices or realised revenue at that checkpoint. Recheck before making launch claims.
- No live Scrapling dependency found in the shared Python venv at audit. Do not pip-install into shared production venv.

## What the market leaders teach (published descriptions, not access to internals)
| Company | Publicly described mechanism | Specific Empire adaptation |
| --- | --- | --- |
| People Data Labs | Ingest many public and partner feeds, normalise/dedupe, QA and legal review before dataset releases | Evidence ledger with canonical entity graph, field/source-level rights, freshness and review receipts |
| Apollo | Public crawling + network/contributor + third-party + engagement/bounces, cross-check | Provider confidence and contradictions, first-party opt-in/bounce signals only with lawful permissions |
| Clay | Multi-provider sequential waterfall by missing field, provider provenance | Existing Empire Waterfall gets per-field source choice, quality, licence, budget and recheck scheduling |
| 6sense | Account-level purchase stage from historical CRM/web/marketing/intent signals | Omega/Buyer Demand Graph should report calibrated opportunities with actual outcome feedback |
| Bombora | Consent-based publisher co-op and relative account-intent baseline | Future opt-in partner network; cannot simply imitate by silently collecting identifiable behaviour |
| ZoomInfo | Broad commercial data + workflow distribution | Vertical-specific fresh datasets + application/portal/API distribution, not pretending to have comparable volume |

**Public primary sources:** https://www.peopledatalabs.com/data-lab/datafication/our-data-build-process ; https://knowledge.apollo.io/hc/en-us/articles/45824429846669-Apollo-Data-Overview ; https://university.clay.com/docs/building-a-data-waterfall ; https://support.6sense.com/docs/intent-model ; https://bombora.com/intent/

## Open-source evaluation (adopt only after owner/dependency/security review)
| Priority | Project / licence | Purpose | Decision |
| --- | --- | --- | --- |
| P0 | Scrapling, BSD-3-Clause — https://github.com/D4Vinci/Scrapling | Adaptive HTML/selector engine for already-lawful source collection | **Add optional parser** in isolated runtime; no default stealth/bypass, live robots/terms review mandatory |
| P0 | Splink, MIT — https://github.com/moj-analytical-services/splink | Probabilistic company entity resolution and duplicate handling | **Benchmark offline** against canonical `business_entities` + `prospect_entity_links`, never auto-merge from fuzzy score |
| P0 | Trafilatura, Apache-2.0 — https://github.com/adbar/trafilatura | Extract meaningful page text/metadata for search/competitor intelligence | **Benchmark offline**; dedupe work with existing Search Intelligence extraction first |
| P1 | Crawlee Python, Apache-2.0 — https://github.com/apify/crawlee-python | Persistent request queues, retry policy, worker management | **Compare with existing crawler runner**; do not install second scheduler unless a measured gap exists |
| P1 | Crawl4AI, Apache-2.0 — https://github.com/unclecode/crawl4ai | Markdown/LLM-aware extraction of difficult pages | **Optional escalation**, CPU/browser limits, never default crawler |
| P1 | Evidently, Apache-2.0 — https://github.com/evidentlyai/evidently | Drift/quality/evaluation for lead scores and prediction | **Reuse current OTEL**, add small reports before a new service |
| P1 | Dedupe, MIT — https://github.com/dedupeio/dedupe | Alternative active-learning record linking | **Compare against Splink**, choose one after gold-set results |
| P2 | OpenMetadata, Apache-2.0 — https://github.com/open-metadata/OpenMetadata | Data catalogue/lineage and governance | **Defer self-hosting**; start with lightweight EmpireDB provenance/schema |
| P2 | Scrapy, BSD-3-Clause — https://github.com/scrapy/scrapy | Established large-scale scraping pipelines | **Alternative**, not in parallel with Scrapling+Crawlee |
| P2 | Common Crawl — https://www.commoncrawl.org/get-started | Public web corpus for source discovery | **Existing exploratory pipeline**; retain rights/recency checks before commercial usage |

Licensing of an open-source **tool** does not convey a licence to scrape, retain, resell, or contact people identified in third-party **data**. Review target-site ToS/robots and applicable privacy and marketing rules separately. See UK ICO: https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/

## Canonical intelligence graph and missing runtime proofs
1. **Source Intelligence & Legal Intelligence**: `source_intelligence.py` + evidence of licence, allowed_use, robots/terms, geography; *code present*, per-source activation **not verified**.
2. **Scrapling evidence bridge**: `scrapling_source_evidence.py`; bounded offline source observations, SHA-256 document reference, no outbound and no canonical insert. **Implemented in this branch; optional Scrapling dependency absent**.
3. **Identity resolution**: normalize domain/company/address/regulatory number to canonical `business_entities`, `prospect_entity_links`, with cross-source contradictions and human review. **Automated linkage of new Scrapling records not built**.
4. **Evidence enrichment**: `prospect_enrichment.py`, `evidence_enrichment_planner.py`, site crawl and waterfall. **Code present**, source-specific fresh evidence receipts for new records not yet validated.
5. **Qualification/Scoring**: `lead_scoring_v2.py` and `qualification_worker_v2.py`, plus `intelligence/omega.py` and `omega_worker.py`. Never treat scraped volume, email existence or SEO traffic as buyer readiness.
6. **CORTEX feedback**: `cortex_learning_loop.py` should consume *genuine* buyer, payment, fulfilment, complaints and refunds. Previous snapshot stale (22 Sep). No model-accuracy claim until outcome-labelled evidence exists.
7. **Demand & Signals**: `buyer_demand_graph.py`, `predictive_intelligence.py`, Search Intelligence, permits, property and `market_sweep_revenue_gps.py`: tie signals to exact business, niche, geography and observation time, else display disconnected.
8. **Predictive Cloud**: predict narrow vertical/corridor fulfilment economics with known uncertainty, calibrate against actual outcomes, not only arbitrary heuristic scores. Live lead-level evidence join **not verified**.
9. **Buyer commercial authority**: `buyer_allocation.py` and exchange: explicit verified buyer, deal terms, route, price, active capacity, expiry and destination. A seat record does NOT imply a paying buyer.
10. **CRM / Self-Serve / Brokerage**: evidence-backed niche counts and permissions; raw personal details not bulk exported without lawful use and delivery rights. Differentiate company identity count, contact discovery, qualified, available-to-buy, delivered and paid.
11. **Economic Memory**: `economic_memory.py` accepts confirmed realised cash/payment+fulfilment receipts; feed actual source ROI and response outcomes back to Demand/Sourcing. Never turn forecasts into revenue.

## Commercial product architecture
- **Verified Leads:** niche/metro snapshots with provenance, freshness and independently qualified count. Separate enterprise prospect discovery from homeowner consumer enquiries.
- **Territory Capacity / Lead Seats:** buyer-specific, expiring, contractual caps; no invented exclusive availability.
- **Data Brokerage:** enterprise intelligence/API snapshots only with row- and field-level redistribution rights.
- **Predictive Revenue Intelligence SaaS:** paid access to aggregated opportunity gaps, pipeline and outcome dashboards where rights permit.
- **Enterprise / White Label:** tenant-isolated endpoints, auditable lineage, SLAs, dispute records, opt-outs and human-admin approvals.
- **First-party demand channels:** zero-spend SEO/AEO/GEO and content niches, referrals, partner publisher opt-ins; no behavioural tracking claims without consent.

## Proposed 3-horizon execution
### Horizon 1 — launch-worthy evidence, £0 spend
- Reconcile EmpireDB total unique prospects by niche/territory against the 176 bounded exchange subset; show completeness and freshness flags.
- Add optional Scrapling source parsing (this branch), lawful-source review and offline gold fixtures. No live network crawling by default.
- Benchmark Splink/entity linking on a labelled 100–500 record sample; gate merges on false-positive rate and human review.
- Produce source-by-source yield: requests, approved pages, observations, unique canonical companies, qualified, buyer-ready, offered, paid. Never count events as leads.
- Focus first paying buyer: UK solar or US roofing as supported by actual buyer evidence, not vanity traffic.
### Horizon 2 — profitable niche product
- Trigger enrichment only for unverified fields and observed buyer-demand gaps.
- Add suppression, per-field provenance, refresh age, source terms history, score calibration and delivery dispute reporting.
- Private self-serve preview with demand/territory coverage, paid-capacity limits and prospect-to-delivered ledger; real checkout remains separately approved.
### Horizon 3 — defensible commercial network
- Source/partner contribution agreements and explicit data-rights governance; multi-tenant API, SLAs, licensing, vertical coverage.
- Opt-in cooperative signals and first-party outcomes; predictive pricing with proven demand and margin.
- Expand UK/US niches only after customer acquisition, retention and realised margin justify compute and rights expense.

## Prioritisation metric
Reward **verified realised contribution margin per niche/corridor**, paired with independently verified source freshness, cross-source agreement, delivery success, unsubscribe/suppression safety and buyer satisfaction. Lead volume alone is neither recurring revenue nor customer value.

## Delivery in THIS branch
- `empire_os/scrapling_source_evidence.py`: Scrapling-compatible offline parser and evidence contract, rights/robots/terms/privacy manual-review gates, strict source-domain, bounded rows, dedupe, no network and no CRM/DB writes.
- `tests/test_scrapling_source_evidence_20261019.py`: no-network synthetic source tests.
- No public deployment, no new service, no runtime package change, no customer activation.


## Verification receipt — 19 October 2026
- Temporary isolated Scrapling parser installed under `/tmp/empire-scrapling-20261019` ONLY to validate real CSS extraction. Shared `/srv/empire_os/.venv` remains unchanged.
- 70 tests passed on this isolated integration branch, including the real Scrapling offline HTML fixture, source-domain controls, URL/port policy holds, rights-reference enforcement, bounded deduplication, lead-supply and intelligence bridge regressions.
- Static edge audit: 11/11 component source and sink files exist; **0/11 runtime connections established by this audit**.
- New evidence proposals carry review evidence references; the tests use synthetic references only. Actual terms, robots and lawful-use reviews must occur before collecting any third-party website.
- Source link extraction does not prove website ownership, identity, email deliverability, consumer consent, rights to resell, commercially committed buyer seats or revenue.
- Implementation remains unmerged and unactivated pending a named owner review and source-specific pilot.
- For a bounded code-edge audit: `/srv/empire_os/.venv/bin/python -m scripts.review_revenue_data_fabric_20261019 --read-only` from the isolated worktree.
