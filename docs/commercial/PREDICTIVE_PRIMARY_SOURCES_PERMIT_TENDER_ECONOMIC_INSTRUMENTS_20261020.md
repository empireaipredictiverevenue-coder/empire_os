# Empire AI Predictive Revenue — Primary Sources, Permit/Tender Economics and Expansion Plan

**20 October 2026 | Isolated Predictive Decision Control feature branch | no production deployment or new paid provider**

## Commercial strategy: source quality above source quantity

Newsjack/JEV is the event discovery and organic relevance owner. Predictive consumes its reviewed evidence; it must not run another news crawler or pretend search trends are buyers. The next *different* primary sources needed are original **project activity**, **contract procurement**, **labour/material input costs**, **licensing/eligibility**, **climate exposure** and **authenticated purchase/outcomes**. Each serves a different part of the north star:

**Predicted Gross Profit → Realised Gross Profit → Prediction Error → Better Allocation.**

A news article can signal research urgency; a permit can evidence a filing; a tender can evidence a public buyer's published procurement process. Only original signed terms, payment and attributable costs can evidence that Empire actually earned money.

## Existing EmpireOS source owners discovered; preserve their jobs

- `permit_project_intelligence.analyze_permit_project_intelligence` analyses original NYC permit inbox, source filing/issuance date versus import date, original official provenance and property/buyer role ambiguity; no outbound or DB writes.
- `permit_product_integration`, `permit_source_revision` and `permit_intelligence_runtime` already manage permit product and source readiness.
- `uk_public_tender_observer.normalize_uk_tender_releases` processes at most 5 official Find a Tender OCDS releases per call, checks CPV niche classifications and explicit tender stage. It does not treat tender notice as award.
- `uk_tender_incremental` already owns cursor/watermark semantics; do **not** create another tender feed worker. A first page is not evidence of a complete source window.
- `companies_house_identity` and `source_intelligence` already cover UK business registry and licensing/source use policies.
- `flagship_geo_material_context` and `storm_intelligence_runtime` already cover market/geophysical evidence boundaries and current storm-data freshness.
- `economic_signal_fabric` and `predictive_market_economic_twin` already own normalized signals and hypothetical economic shocks. Do not invent a new optimization engine.

## Built now

### Original Permit + UK tender owner adapter

`empire_os/predictive_primary_source_economic_bridge.py`

- `review_existing_permit_owner(packet,as_of)` accepts the original `empire.permit_project_intelligence.v1` result, validates research-only authority, source store, origin clock, bounded counters, recent-vs-historical filing date truth, selected 5-or-fewer original dossiers, and privacy constraints. It **never emits owner/permittee names, phones, property addresses, direct commercial URLs or record details**.
- `review_existing_uk_tender_owner(packet,as_of)` accepts original `empire.uk_public_tender_observation.v1` owner results; verifies official publisher/source/attribution, research rights from the existing Source Intelligence pack, fresh owner epoch, page size <= 5, stage and count consistency, official CPV group, and semantic original source revision. A public tender is never counted as contract award, accepted bid, purchase, payment, geographic delivery match or profit.
- `build_primary_source_economic_review(permit,tender,as_of)` keeps local US permit cohorts and country-level GB tender observations **separate**; proposes only original owner research work, requires real capacity/cost/purchasing/forecast/profit proof and does not alter any existing system.

**Live private read-only operator** (the permit owner runs locally against source-owned inbox, no web):

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_primary_economic_sources_20261020 --read-only

# Optional: when UK tender owner has exported a reviewed source result
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_primary_economic_sources_20261020 \
  --read-only --owner-uk-tender-review /approved/existing-owner-output.json
```

The operator never contacts Find a Tender; it reads a permitted owner-reviewed packet only. An unavailable UK tender review returns **unknown**, not zero opportunities.

### Actual observed Permit state, 20 October 2026

- 193 entries of the `permits_nyc` source type were present in existing acquisition inbox.
- 136 records in the 24-hour *import* cohort.
- **0** source-verified new filing/issuance events in that cohort.
- **136** historical project-source records, despite having been recently imported.
- 136 source URLs passed original permit source provenance.
- **0** independently verified purchasing terms, commission or real profit from this review.

These counts are specific to the original owner's available source and sampling window; they are not the entire city, nor evidence that no recent permits exist.

## What else we should connect, without duplicating collectors

### 1 — Best next for forecasting unit costs: official labour and materials indices

**U.S. BLS Public Data API (v2)** for carefully chosen PPI and employment/wage series: https://www.bls.gov/developers/api_signature_v2.htm

Use **time-specific, geography-appropriate indices** to stress market-twin assumptions for labour shortages, installed component inflation, roofing/HVAC parts, construction inputs. An index level or inflation rate is **not a supplier quote**, payroll cost or source-authenticated COGS for a specific job. The original Finance/Materials owner must connect actual costs separately.

**Measurement:** original series ID, release/period, revision, units, seasonal adjustments, vintage; track forecast error *versus owner-reported actual material/labour spending*.

### 2 — Best for location/market activity: Census Building Permits + local original permit agencies

U.S. Census Building Permits Survey: https://www.census.gov/construction/bps/index.html

Monthly/annual U.S. state, county, CBSA and place level housing-unit permits. High signal for **construction activity by geography**, low proof of what specific customer will buy or whether a permit is still active. Different unit of observation from NYC DOB. Do not sum local filing records and aggregate permits as unique leads.

**Measurement:** permit authorizations per geography/period, vintage revision, zero versus missing counties, original owner job activity, late materialisation rate. Source/municipal agency verification required.

### 3 — Best for Storm calibration: NOAA NCEI Storm Events

NOAA historical Storm Events Database: https://www.ncei.noaa.gov/access/storm-events-database/

Useful for retrospective storm severity/event history, seasonality, lag calibration and geography, not for current live storm warnings or automatic property damage claims. The Storm/Spatial owner already has relevant hooks; feed historical calibration **only after event/location IDs and source epochs match**.

### 4 — Strong for UK/US procurement: existing Find a Tender + Contracts Finder and SAM.gov

UK official OCDS publication: https://www.gov.uk/government/publications/open-contracting

SAM.gov official opportunities: https://sam.gov/opportunities

Use source stage, published CPV/NAICS category, published deadlines, buyer department, amendments and later independently verified awards. Notice ≠ award; award ≠ Empire's revenue. Keep supplier-specific licence, procurement procedure and bid eligibility checks with the original procurement/commercial owner. The UK Find a Tender source is already covered; do not create a second connector. SAM.gov is a candidate requiring rate/key/terms review, not a connected source.

### 5 — Strong for solar / heat pumps / grid: national regulator + grid connection/install data

Ofgem historical FIT installation reports: https://www.ofgem.gov.uk/feed-tariffs-fit/contacts-guidance-and-resources/public-reports-and-data-fit/installation-reports

Useful **historical solar adoption/density and sector change**, not live solar buyer identity or current accepted installation pricing. The existing Source Intelligence pack already registers `gb_ofgem_fit`. Add permitted original grid queue/interconnection and installation-series sources by country only with source-owner rights review. Model market penetration and grid delays carefully; do not confuse historical adoption with near-term conversion.

### 6 — Valuable for commercial entity resolution: Companies House / registries / certifications

Companies House API: https://developer.company-information.service.gov.uk/get-started

Verify original corporate identity, status, role, filings, territory and entity resolution, alongside original contractor licensing directories (MCS, RECC, TrustMark). Business registry status does **not** authenticate an officer as your sales decision-maker or prove buying authority. Existing `companies_house_identity`, `source_intelligence`, and buyer qualification own that. Never reuse personal/third-party contact details for automated outreach without authority.

### 7 — Further model inputs: market conditions, product performance, energy costs and logistics

Official utility tariffs, regulator programmes, public grid constraints, fuel/travel costs, weather/seasonal hindcasts, verified service times, cancellations, returns and customer adoption trends all affect economics. U.S. PVWatts v8 can estimate *solar energy yield* under assumptions; yield ≠ installed system profitability or a sale (https://developer.nlr.gov/docs/solar/pvwatts/v8/). Treat each model as a source-specific estimator with validation against observed outcomes.

## Original owner division and release gates

- **Source owners** independently verify licensing, raw provenance, timestamps, update policy, jurisdiction, completeness and source errors. No unapproved crawling.
- **Spatial / Knowledge Graph** binds geographic identifiers and asset/market sector without string-only metro guesses.
- **Materials / Finance** maps current published indexes to explicitly hypothetical cash/COGS shocks until original invoice amounts and supplier quotes exist.
- **Buyer/Commercial** validates actual buying decision-maker, approved terms, deliverable capacity, lawful contact routes, settlements.
- **Scientific Quant** prospectively registers the original cohort prediction before events and outcomes; accumulates missing and negative labels, not selected successes only.
- **Existing Predictive Decision Control** converts reviewed observations into what-if scenario *proposals*, measures ROI and can issue a governed recommendation when original outcomes/permissions allow.
- **Economic Memory** only learns verified prediction error from original matching revenue/GP outcomes.

**No new service, source crawl, subscriber/advertising cost, scraping, model training, outbound message, bid, website mutation, payment or production data write.** This implementation is a source-evidence integration in the existing Predictive feature branch, not a deployed direct-revenue campaign.
