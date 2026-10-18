# Empire AI — DOB NOW + Building Footprints + PLUTO: official property evidence

**18 October 2026 | Existing Property / Market / Warehouse / Data Brokerage | zero paid providers, no outreach, OBSERVE**

## Purpose and exact source identities

Extend the actual existing DB-NOW permit intelligence lane **without inventing another data warehouse or CRM**:

- NYC Department of Buildings (DOB), two published DOB NOW datasets: initial issued-permit `rbx6-tga4` and original filing `w9ak-ipjd`, already cross-matched by source job, BIN, BBL and original event dates.
- NYC Office of Technology and Innovation (OTI) **Building Footprints**, dataset `5zhs-2jue`, latest portal snapshot 5 October 2026 at time of review. `bin` is the city building reference and `base_bbl` identifies the tax lot on which the footprint lies; this is **not** a property ownership record or physical-site inspection.
- NYC Department of City Planning (DCP) **PLUTO 26v2**, dataset `64uk-42ks`, snapshot 24 August 2026. `bbl` is a tax lot; `landuse` is its category. One tax lot can contain multiple buildings. This snapshot **predates** the October issued permits.

Public official datasets:
- https://data.cityofnewyork.us/d/5zhs-2jue
- https://data.cityofnewyork.us/d/64uk-42ks
- https://data.cityofnewyork.us/d/w9ak-ipjd
- https://data.cityofnewyork.us/d/rbx6-tga4
- https://www.nyc.gov/assets/planning/download/pdf/data-maps/open-data/pluto_datadictionary.pdf

## New evidence quality taxonomy

A project event is **TRI_AGENCY_BIN_AND_LOT_MATCH** only if the DOB job's exact official BIN and BBL match the OTI building footprint's exact BIN/**base** BBL and one matching DCP PLUTO lot record in the same borough. Ambiguous multiples, absent BIN, absent lot, and mismatching OTI base lot are separate states.

- `TRI_AGENCY_BIN_AND_LOT_MATCH` — chain of *published government references* corroborated, **not** proof of current site activity, project ownership, or actual physical asset use.
- `DCP_LOT_ONLY_BIN_UNCONFIRMED` — DOB tax lot exists in DCP PLUTO but building footprint identity is not corroborated.
- `BUILDING_TAX_LOT_CONFLICT` — DOB and OTI disagree on building's base tax lot; cannot resolve by pretending one is right.
- `DCP_BOROUGH_CONFLICT`, `AMBIGUOUS_SOURCE_IDENTITY`, and `PROPERTY_SOURCE_REFERENCE_UNMATCHED` — explicit holds, not data dropped to boost apparent quality.
- `DCP land use 01/02/03/04/05/06...` — **tax-lot** context; industrial/manufacturing `06` is a source-defined category and **does not establish an operating warehouse**, a tenant, a commercial contract, a roof job or a buyer.

The selected-field queries do **not request** building names, owner names, applicant, mailing address, phone/email, raw polygons or individual street addresses. External traffic is limited to fixed official city API URLs and <=40 DOB events / <=120 result rows per source query, with 15-second HTTP timeouts, response-size limits, exact-source-response SHA-256, reproducible source selection, and no paid service.

## First live sample: 18 October, recent DOB NOW permits

The actual bounded `current_event_sample` first-page reader provided 36 distinct validated DOB NOW job-event references from 40 official initial-permit rows. **This is a partial sample**, not all city events or all unique physical buildings.

Joined to both OTI footprint and DCP PLUTO:

| Outcome in 36 permit-event sample | Count |
| --- | ---: |
| Tri-agency reference chain matches | **25** |
| Only DCP lot matches; OTI building BIN unconfirmed | **10** |
| Conflicting DOB-vs-OTI base BBL | **1** |
| DCP category 05 (commercial/office) tax-lot context | **6** |
| DCP category 06 (industrial/manufacturing) tax-lot context | **0** |
| Verified operating warehouses, property ownership, paying buyers | **0** |

**Specific quality alert:** DOB NOW job `B01222111-I1` uses DOB BIN `3002642`, official source BBL `3002697501`, but matching OTI building footprint BIN `3002642` reports base BBL `3002690001`. DCP PLUTO has the original DOB lot BBL. This is a genuine cross-agency source discrepancy; do not silently join this job to a building/lot as trustworthy without further source-specific investigation.

Tax-lot context distribution in the 36-event sample: 6 commercial/office; 1 mixed residential/commercial; 3 multifamily elevator; 9 multifamily walk-up; 9 one/two-family; 1 parking; 2 public/institutional; 1 vacant land; **4 unknown**. All are source-defined lot categories, not newly verified business prospects.

The resulting private artifact remains original derived Empire AI analysis of independently published third-party records with explicit agency attribution and SHA-256 source response evidence. **No automatic third-party dataset resale is authorised**; source-usage and attribution constraints require review before any customer export.

## Existing systems integration and ownership

New:
- `empire_os/permit_property_source_join.py` — read-only, bounded, three-agency reference chain validator with industry context and source data quality diagnostics.
- `empire_os/property_source_evidence_runtime.py` — accepts a small, local, validated optional research packet and returns **sanitised counts only**, never names, contacts, full public records, property owners or property opportunities.
- `scripts/review_dobnow_building_landuse_readonly.py` — defaults to source read/summary only. Explicit `--record-private` stores one `0600` latest internal derived report plus its provenance receipt in **existing** `runtime/data_brokerage`. No live DB/CRM mutation.
- `tests/test_permit_property_three_agency_20261018.py` — source cross-check, conflicting BBL, missing BIN, ambiguous duplicates, zero buyer/warehouse proof, injection and bounds.
Updated existing:
- `empire_os/vertical_intelligence_runtime.py` — extends existing Property Intelligence with `three_agency_source_reference_review` only; does not inflate legacy `evidence_count`, opportunity count or canonical property identities.
- `empire_os/source_intelligence_handoff.py` — existing Property and Warehouse department handoffs receive **sanitised source quality counts**, not customer or third-party raw records. No new lane, queue, scheduler, paid model or autonomous campaign.

## Remaining open work

- Complete cross-agency matching across **all daily DOB source-issued events** (the cursor/day coverage reader is committed separately but source activation is still OFF); more one-day samples should be selected through existing data-read capability, not additional crawlers.
- Official footprint BIN and DOB BBL disagreements need targeted official building-reference adjudication, not manufactured certainty.
- Land-use 06 classification supports **potential industrial-tax-lot context** only. Verify actual building usage/occupancy/warehouse operation via a separate time-aligned source before creating marketable asset insight.
- Property ownership, site-level permit scope, parcel/building geometry consistency, data rights, actual changes, private claims, buyer capacity and payments remain unverified.

**Explicit scope:** Existing EmpireDB remains canonical, no Supabase. `EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED` stays UNSET. No new timers, ports, services, database tables, sender tasks, budget commitments, public site changes or commercial contact actions. This milestone is **data product evidence integrity**, not a claim of revenue.
