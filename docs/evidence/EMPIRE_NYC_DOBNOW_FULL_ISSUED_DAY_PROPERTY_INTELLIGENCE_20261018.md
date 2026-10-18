# EmpireOS — complete DOB NOW day to three-agency building and tax-lot intelligence

**18 October 2026 | Existing Data Brokerage, Property, Market and Warehouse Intelligence | OBSERVE, no commercial activation**

## Concrete milestone

The earlier first-page sample of 40 DOB NOW initial-permit source rows (36 distinct cross-checked jobs, of which 25 had complete DOB–OTI–DCP reference chains) **was not full-day evidence**. This release reuses the existing exact-date DOB NOW `:id` cursor reader and filtered official daily count to reconstruct one **fully count-reconciled issuance-day observed snapshot**. It then reuses the bounded OTI building-footprint BIN and DCP PLUTO tax-lot property matcher in successive <=40-job chunks and creates one private, individually auditable original-derived research packet. It never turns a building record into a verified owner, buyer, contractor, operating warehouse, insurance claim or actual site visit.

**Source-key correction:** Official NYC OTI Building Footprints metadata explicitly defines `BASE_BBL` as the physical building footprint lot and `MAPPLUTO_BBL` as the correct PLUTO join key (with condominium billing-lot aggregation). Published DCP PLUTO documentation describes condo billing lot numbers typically 7501–7599. This is why comparing DOB-issued billing BBL exclusively to physical BASE_BBL falsely flagged 24 entries. Reference: https://github.com/CityOfNewYork/nyc-geo-metadata/blob/main/Metadata/Metadata_BuildingFootprints.md and https://data.cityofnewyork.us/d/64uk-42ks

Official sources: NYC DOB NOW Build Permit Issuance `rbx6-tga4`, NYC DOB NOW Job Filings `w9ak-ipjd`, NYC OTI Building Footprints `5zhs-2jue`, NYC DCP PLUTO 26v2 `64uk-42ks`. The city retains authority to correct these sources. A matching published building reference is not proof of construction underway. PLUTO 26v2 (August 2026) predates the 16 October permit issuance.

### Real live-source results (18 October 2026, issued day 16 October 2026)

| Specific source-evidenced metric | Observed |
|---|---:|
| Official initial-permit rows, counted **before** read | **444** |
| Official initial-permit rows reconstructed through 12 bounded `:id` pages | **444** |
| Official initial-permit rows, counted **after** read | **444** |
| Distinct DOB NOW job filing references after consolidating work permits | **312** |
| DOB BIN + OTI building physical BASE_BBL + DCP lot match | **236** |
| DOB BIN + OTI MAPPLUTO_BBL condominium/billing-lot + DCP lot match, physical base lot differs | **24** |
| **Total confirmed DOB–OTI–DCP reference chains (not unique physical sites)** | **260** |
| DOB BBL differs from both OTI base and MAPPLUTO BBL (unresolved reference discrepancy) | **9** |
| DCP tax lot matches, OTI building BIN unconfirmed | **41** |
| OTI BIN present but DCP tax lot missing | **1** |
| Neither building reference nor tax-lot match | **1** |
| Commercial/office PLUTO tax-lot category, irrespective of building trust state | **73** |
| Industrial/manufacturing PLUTO tax-lot category, irrespective of building trust state | **5** |
| Industrial/manufacturing PLUTO tax-lot with corroborated three-agency reference chain | **4** |
| Physically operating warehouses, verified owners, paying customers or realised revenue | **0 verified** |

The observed 312 jobs **cannot** be equated to 312 unique real-world construction sites or separate assets. Multiple DOB jobs and BIN references can map to one building/lot. Four industrial-lot candidates are tax-lot classifications and reference matches only, **not verified warehouse operations**. The original 33 apparent base-lot conflicts were not all actual DCP-join conflicts: **24 reconciled** through OTI MAPPLUTO_BBL, the city-documented correct DCP join key for condo billing lots. **Nine** remain unresolved, including a group of records on one Bronx block. Do not conflate permit-job counts with distinct physical building counts.

These numbers came from a single live **read-only** cross-source exercise. The one-day count is an official source snapshot at the observation time, not a serializable government-data transaction; identical counts cannot rule out within-period edits or a later backfill.

### Reuse, source truth, and protections

- `empire_os/permit_property_full_day_review.py`: synchronously iterates the existing keyset DOB reader, checks the same official initial-issued-day row-count before and after scan, requires every row accounted for, reuses the current DOB source project merger and the existing three-agency property matcher; prevents incomplete or internally inconsistent results.
- Max **30 x 40** official DOB rows / on-demand single-day review (1,200 bounded), <=40 verified job references per OTI/DCP query, no paid endpoints, no new timer/agent/database. A day >1,200 rows is a **hold**; no silent incomplete/day label.
- `scripts/review_dobnow_building_landuse_readonly.py --issued-day YYYY-MM-DD`: read-only result summary by default. An explicit `--record-private` writes a new derived report to `runtime/data_brokerage/nyc_dobnow_property_three_agency_full_day_latest.json` and SHA-256 receipt `...provenance.json`, mode 0600, without overwriting the original smaller `nyc_dobnow_property_three_agency_latest.json` 36-job sample. Includes selected API JSON SHA-256 per DOB page and OTI/DCP chunk, source count proofs, observational timestamp and guarded source categories.
- `empire_os/property_source_evidence_runtime.py` prefers the fully reconciled research packet when available, validates count/page/chunk/diagnostic status totals and per-job uniqueness, then exposes **only aggregate counts**, never raw property references or identities. It continues to accept the previous 36-job v1 packet when no v2 exists. Rejects invalid, future-dated, stale or contradictory source packets, and never falls back from an invalid full-day packet to misleading earlier partial data.
- `empire_os/source_intelligence_handoff.py` already owns the Property/Warehouse lanes. It now exposes `full_issued_day_source_count_reconciled`, `reviewed_official_permit_event_count`, reference matches/conflicts and industrial-lot-context counts. It does **not** inflate `verified_property_opportunity_count`, `warehouse_operation_verified_count`, revenue, CRM, prospect queue, outbound permission or actual industry operation.
- `tests/test_permit_property_full_day_20261018.py` verifies exact-day counts, 3-page resume, independent OTI/DCP join, reader/department integration, duplicate conflict bounds, source count-change hold, raw source row overrun, unsupported day, fabrication/forgery rejection and v1 backward compatibility.

**Originality and rights:** derived original Empire AI annotations and evidence-quality classifications from independently published official data; underlying government data remain attributed third-party source records. External redistribution and source-specific licence terms must be separately checked. No website page updates, consumer records, SMTP sender, paid traffic, money movement or customer-facing feed occurred.

**Remaining gap:** full date capture is now demonstrably possible on demand, but automated DOB NOW scheduled source activation remains OFF. Other dates are not claimed complete, nor are historical corrections or full unique-site/building and ownership verification. Next internal quality milestone: investigate the nine remaining different-physical-base-and-billing-lot references using additional official building/parcel history, then distinguish genuine warehouse/solar/office operational activity from tax-lot labels without guessing.
