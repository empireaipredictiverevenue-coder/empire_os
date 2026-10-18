# Empire AI — 18 October 2026 official NYC Permit + Property evidence milestone

**Existing EmpireOS Data Intelligence / Data Brokerage / Market Intelligence / Property Intelligence. No outbound. No scheduler or new ingestion service.**

## Observed live source milestone

On 18 October 2026 the canonical Ubuntu EmpireOS research environment queried two **free primary NYC Department of Buildings** published source streams and joined five records across them. This **closes a small, specific validation gap**, not the larger automatic-scheduled ingestion/product/rights work.

| Primary source | Dataset ID | Selected event-date field | Observation |
| --- | --- | --- | --- |
| NYC DOB NOW: Build – Job Application Filings | `w9ak-ipjd` | `filing_date` and `first_permit_date` | Fetched live, HTTP 200. Reports **1,220 filing rows** where actual filing date >= 15 Oct 2026; **18 filing rows** marked `solar_work_type_ = YES` on 16 Oct |
| NYC DOB NOW: Build – Approved Permits | `rbx6-tga4` | `issued_date`, `filing_reason` | Fetched live, HTTP 200. Reports **942 initial-permit rows** with issuance date >= 15 Oct; **444 initial-permit rows dated exactly 16 Oct**; **0 initial-permit rows dated 17–18 Oct** at the bounded check |
| NYC Department of City Planning — PLUTO | `64uk-42ks` | static `26v2` tax-lot version, updated 24 Aug 2026 | Fetched live, HTTP 200. Matched five out of five selected BBL tax-lot numbers from the DOB sample. **Not** contemporaneous proof of a property change |

**Important interpretation:** These numbers are official dataset **row counts**, NOT counts of unique new projects, live active building sites, property owners, companies, warehouses, roofing jobs, insured losses, buyer demand, sales leads or payable events. Jobs may include revisions or multiple work permits; a newly issued permit can relate to a filing months earlier. The NYC portal can amend/correct data after this read.

The existing old BIS-derived `runtime/acquisition/signal_inbox.json` and 5-minute department source packet were independently observed at ~11:03 UTC: **62 recently imported but historical original project events** in its rolling cohort, **zero real events within 30 days**, with **7,765 retained NYC permit observations**. That OLD source cohort is not contradicted by new genuine DOB NOW records: the feeds cover different submission systems. Do not replace old-source counts with these counts without explicit source-specific ingestion and deduplication.

## Five concrete original event-date cross-checks

Selected **Brooklyn** examples: exact official DOB NOW job filing ID in the Approved Permits dataset equals the ID in the DOB NOW Job Application Filings dataset. Both sources have identical `borough`, `bin` and `bbl`; `issued_date` and `first_permit_date` both equal 16 October 2026. All five approved-permit rows are `Initial Permit`, `General Construction`, `Permit Issued`.

| Official job filing ref | Original filing | First permit / issuance | Observed actual change |
| --- | --- | --- | --- |
| `B01222111-I1` | 2025-05-08 | 2026-10-16 | First General Construction permit |
| `B01313771-I1` | 2025-12-10 | 2026-10-16 | First General Construction permit |
| `B01319969-I1` | 2025-11-27 | 2026-10-16 | First General Construction permit |
| `B01338779-I1` | 2026-02-10 | 2026-10-16 | First General Construction permit |
| `B01408259-I1` | 2026-08-13 | 2026-10-16 | First General Construction permit |

This is **five verified cross-dataset source-event joins**, not five independently inspected job sites. The two DOB datasets belong to the same original NYC DOB agency; they are consistent evidence of published official permit state, **not external/third-party confirmation of a project's physical state or buyer identity**. None of five is proved to be a roofing or solar contract by General Construction work type alone.

The bounded **DCP PLUTO 26v2** land-use/tax-lot join then matched each selected DOB BBL to one NYC Planning record:
- 5/5 tax-lot references matched across **separate DOB vs DCP agencies**.
- Source land-use category codes included 1, 2, 4, and one missing value (missing means UNKNOWN); matching tax lot does **not** prove an individual building or current owner.
- Storage/factory area not shown as positive in this bounded sample; **zero warehouse or manufacturing opportunities proven**. Land-use and building-class attributes are contextual source labels, not inspection results.
- The August DCP version predates October permits; no site-use change is proven.

## Private provenance and original Empire AI derived evidence

All four files generated under **existing** `runtime/data_brokerage`, mode **0600**:

1. `nyc_dobnow_cross_source_first_permits_20261018.json`
2. `nyc_dobnow_cross_source_first_permits_20261018.provenance.json`
3. `nyc_dobnow_pluto_taxlot_join_20261018.json`
4. `nyc_dobnow_pluto_taxlot_join_20261018.provenance.json`

- DOB original **selected-field** research/report SHA-256: `03122e865bfee987685ff2033f3c3ec882cbd9af1c70f841d9b7aa93f5e05cdb`
- DOB + DCP tax-lot original derived report SHA-256: `d40d94eb0a0b3f038395c56d5324b24720484b26480df3976fdbcc27c0abdc5a`
- Each private receipt retains source API query URL and SHA-256 of exact returned JSON body, observation UTC, founder-directed AI assistance, third-party-source attribution, and no C2PA or third-party ownership assertion.
- Only source event/status/ref/coded-use fields were fetched: no applicant/owner names, private contacts, individual addresses, recorded calls or consumer/claimant data. No raw full source export, EmpireDB insertion, email, paid API, paid model, external distribution, sitemap or website mutation.

Official portals and rights:
- DOB NOW filings: https://data.cityofnewyork.us/d/w9ak-ipjd
- DOB NOW approved permits: https://data.cityofnewyork.us/d/rbx6-tga4
- DCP PLUTO: https://data.cityofnewyork.us/d/64uk-42ks
- Portal terms: https://data.cityofnewyork.us/stories/s/Terms-of-Use/k9k7-3cje
- NYC Open Data official FAQ: https://www.nyc.gov/opendata/get-started/FAQs
- NYC legal standard: public raw datasets available without licence/use restriction generally, but preserve attribution, data version and modification method and honour any dataset-specific terms and accuracy disclaimers. This audit is NOT a review of customer redistribution rights for every source/field.

## Department handoff / registered gap disposition

- **Permit / Market Intelligence:** SOURCE GAP PARTIALLY CLOSED — five real new **issued** event examples. Next step under existing Permit/source owner: decide approved bounded DOB NOW reader integration into existing `signal_inbox`, using a separate source namespace and exact DOB NOW filing ref. Never attempt to reinterpret DOB NOW alphanumeric filing number as the old BIS numeric job ID or synthesize legacy portal links.
- **Property:** first cross-agency tax-lot BBL context confirmed; **building/ownership/transaction verification is NOT closed**. Cross-match the exact structure via official BIN/building geometry only with corroborated distinct-source property records.
- **Warehouse / Industrial:** not yet an industrial shortlist. Join industrial/warehouse land-use codes in a correctly scoped property feed first, then inspect actual industrial assets, rather than labelling any general permit as a warehouse event.
- **Storm:** retain `OBSERVE`. No actual damage, claim or weather-to-property occurrence verified; requires dated primary weather/geospatial match.
- **Solar:** 18 actual 16 October DOB NOW filing **rows** marked `solar_work_type_=YES` indicate a better research slice; source field flags do not establish actual installed solar capacity, system specs or completed contract.
- **UK planning / Brownfield, Insurance/Carrier, legal firm-side, SEO/Common Crawl and founder-origin provenance:** existing queues and source-rights safeguards remain active/unchanged.

**Gates:** no new service, timer, database, Supabase, autonomous mailing, sales promotion or write to original city-source data. No separate payment, checkout, public customer feed or consumer export. **Independently realised brokerage revenue remains $0.**

**Original completion status:** bounded live current-source validation plus reproducible original private evidence and independent DCP tax-lot reference corroboration. **Automated ingestion, source event change capture and distribution rights review remain open.**
