# EmpireOS free-source download → own brain → department intelligence

**18 October 2026 | Founder instruction: no paid data/API services; use existing first-party intelligence, downloaded public sources and canonical EmpireDB.**

## The exact previous downloaded batch

On 16 October the approved Common Crawl 2026 July/August/September **domain-level hyperlink graph** was downloaded to the existing EmpireOS server, not purchased:
- `/home/ubuntu/empire_reviews/seo_roofing_solar_wat_pilot_20261016/approved-2026-domain-graph/cc-main-2026-jul-aug-sep-domain-vertices.txt.gz` (975,916,959 compressed bytes).
- `.../cc-main-2026-jul-aug-sep-domain-edges.txt.gz` (8,619,205,382 compressed bytes).
- Existing official-derived review: `approved-referrer-quality-review.json` (774,979 bytes; SHA256 prefix `b5f277a03ce10102`).
- This review contains **1,974 historical domain relationships** involving **1,870 distinct historical source domains** (including **96** source domains crossing target sets), targeting Nations Roof, Tecta America, Sunrun and Freedom Forever. It contains **zero verified live backlinks**, no page-level anchor proof, and manual review is required for *all* historical domains. This is a research corpus, NOT a list of backlinks to purchase or a verified lead list.

**Precise correction:** the previous bulk download was indeed completed and graph review facts were saved, but **no EmpireDB bulk record import happened**. Do not call it trained-weight knowledge or claim the raw 9GB graph was imported into canonical Intelligence Fabric.

## What was built in this release

### 1. FREE review material → EXISTING intelligence and Marketing OS

`empire_os/free_dataset_intelligence.py` reads only the bounded *already reviewed* graph JSON and verifies its source kind, dataset release, targets, counts, no paid API, no live backlink proof, no production DB writes, and archive review requirement. It extracts aggregate source facts and immutable review SHA256 only; no uncontrolled bulk domain imports.

`empire_os/source_intelligence_handoff.py` now includes an **optional canonical-only sixth lane** `historical_search_graph → marketing_growth` with the official Common Crawl release URL and bounded research quality counters. The existing 5-minute department cycle and durable work queue handle one review task, no new service, scraper, DB, webhook, scheduled paid model call or email. The team receives a source review, **not an asserted live backlink or sales opportunity**.

Existing sources/owners continue: `permit → market_intelligence`, `property → product`, `private_capital → strategy`, `storm → data_quant`, `warehouse → market_intelligence`.

### 2. Free permit downloads become *versioned observed facts*, not false new leads

The existing `empire_os/signal_inbox.py` previously treated an identical permit as a simple `last_seen_at` increment, leaving old `raw.filing_date`, `raw.issuance_date`, `permit_status` and related event facts unchanged. Therefore a **new issuance or amendment to an existing source record could disappear**, even when the crawler observed it.

`empire_os/permit_source_revision.py` now:
- Matches the exact official NYC DOB HTTPS job source + job number across permitted owner/label changes, keeping one original source ID.
- Accepts only official project-event/status/type and BBL/BIN reference fields with checked types/lengths; never changes owner or permittee contact/name from a later source row and never exports those raw details to a queue.
- Adds a bounded immutable observation-history entry (`source_event_revisions`, max 12 recent entries, monotonic `source_event_revision_count`) with **previous** vs **current** event column value, source run metadata, and observation time. Rejects **older** source-run overwrite.
- Distinguishes `created`, `matched` and `updated_source_event`; a newer source run without changed official *event fields* is not labelled a fresh project.
- Reuses existing inbound signal inbox lock, atomic write, department source fingerprint, Permit/Market-GPS event-date verification and CRM safeguards. No new prospect, claim, sale or payment.

Data changes are now eligible to be *detected* by the existing Source Intelligence SHA/source-state comparison. They are **not automatically eligible for Sales/CRM**: that still requires genuine issuance/filing date, business identity, buyer need, suppression and authorised deal terms.

### 3. The actual "brain" and database boundary

The existing private source-intelligence snapshot and department queue form the **reviewable intelligence layer** and will retain derived source summaries and bounded permit revision histories. They serve existing teams without a new data lake. The canonical economic/customer database remains **EmpireDB**, not Supabase.

This release **does not insert raw Common Crawl data or public permit-owner/contact rows into EmpireDB `intelligence_facts`**. That table requires real canonical entity/source bindings, independently verified provenance and the existing controlled materializer authority; blindly inserting 9GB or creating synthetic companies would break it. The correct future step is a small source-approved/identity-linked facts batch using the existing `empire_os/intelligence_materializer_transport.py` only after its DB activation is explicitly cleared.

Future free-source intake is supported through the existing NYC DOB permits crawler, OSM/Overpass, government feeds, GSC and approved archived Common Crawl research with source-specific rights/freshness checks. Bulk graph downloads are **not** to be repeated daily and should respect machine resources and approved acquisition limits.

## Verification

- Automated unit/replay suite: nine permit revision tests, four archived-graph quality/department-routing tests, and broader 76-test combined source/worker/permit/crawler regression suite passed on the isolated worktree.
- Read-only production input test: current source snapshot had **7,765 retained NYC permit observations**; review discovered a **sixth** Marketing/SEO lane, historical relationships 1,974 / distinct source domains 1,870 / verified live backlinks 0, and confirmed no writes/model/spend.
- Production promotion and work-queue receipts must be verified separately before declaring the feature LIVE. Do not treat an isolated test as activation.

## Next build after this

1. Independently verify truly current NYC permit filing/issuance/amendment events using the official free source, preserving original event dates (not `dobrundate`).
2. Add a **small verified property/owner-company source cross-check** for actual current permit dossiers, not individual claimant or policyholder targeting; route to Product and Market Intelligence.
3. Feed a reviewed subset of Common Crawl domain graph observations into the existing SEO intelligence evidence fabric with `HISTORICAL` flags, source SHA and live verification status; no bulk import and no made-up backlinks.
4. Expand the same data-handler versioned source contract to UK planning, contractor/carrier networks, warehouse/industrial, solar/HVAC, legal firm research, private capital and permitted public registries—all in parallel with sales.
5. Use local model intelligence when existing department token budget/QA permits, with cited evidence and no automatic outbound or payment.
