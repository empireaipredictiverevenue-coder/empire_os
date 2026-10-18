# EmpireOS — property intelligence claim-level official evidence contract

**18 October 2026 | Existing Property / Warehouse / Market Intelligence and Data Brokerage | No outreach**

## Why this milestone exists

The reconciled 16 October official NYC DOB NOW permit day proved 444 permit rows, 312 distinct job filing references, 260 government building/lot reference-chain matches, 9 unresolved source-reference mismatch events across two distinct BIN/BBL pairs, and **4 industrial/warehouse-class permit events on 2 distinct BIN/BBL pairs**. It did **not** prove warehouse trading activity, operating businesses, ownership, buyer demand or revenue. These are observation-level, time-limited public-source assertions, not permanent ground truth. The research used NYC DOB NOW Build filings `w9ak-ipjd`, permits `rbx6-tga4`, OTI building footprints `5zhs-2jue`, and DCP PLUTO `64uk-42ks`, preserving dates, official source response SHA-256 and original internally generated analysis evidence.

The original full-day source receipt is `runtime/data_brokerage/nyc_dobnow_property_three_agency_full_day_latest.json` (verified against its separate SHA-256 provenance). **This source report is not a publisher-signed attestation.** The hashes support local artifact integrity and replay comparison, not legal authentication or actual physical-condition proof.

## Additional independent source inspection, 18 October

On-demand review queries only selected public, non-personal fields for exactly four unique BIN and DOB BBL pairs, using free official sources:

| Project reference pair | Evidence classification | New evidence from official sources | What remains unknown |
| --- | --- | --- | --- |
| Queens BIN `4436582`, BBL `4000290016` | Published OTI footprint BIN and `MAPPLUTO_BBL` agree with DCP lot; PLUTO industrial use 06 | DOF building class `E2` = **contractor's warehouse**; PLUTO published `strgearea=2500` | Warehouse currently operating, owner, tenant, contract, occupation and revenue |
| Bronx BIN `2001177`, BBL `2023620071` | Published OTI footprint BIN/`MAPPLUTO_BBL` agree with DCP lot; PLUTO industrial use 06 | DOF building class `E9` = **miscellaneous warehouse**; PLUTO published `strgearea=2167` | Warehouse currently operating, owner, tenant, contract, occupation and revenue |
| Manhattan BIN `1024686`, DOB BBL `1010147501` | DOB NOW permits and a separately published DOB NOW Certificate of Occupancy dataset match the **same** BIN/BBL, but OTI reports base/mappluto BBL `1010140033` | 18 `CO Issued` rows from the selected DOB NOW CO dataset; supporting DOB reference evidence **does not** resolve conflicting OTI lot | Correct physical/billing lot reconciliation, building occupancy or operator |
| Bronx BIN `2094839`, DOB BBL `2036730002` | DOB permit BBL `2036730002` conflicts with OTI footprint's base/mappluto BBL `2036730001`; both are published PLUTO lots, with differing classifications | No matching DOB NOW CO row **observed in this selected dataset query**; not an assertion that no CO exists anywhere | Source-reference discrepancy, occupancy and ownership |

*Definition authority:* <https://www.nyc.gov/assets/finance/jump/hlpbldgcode.html> (E2/E9 warehouse building class). Class and storage area are **published tax-lot records**, not verified present-day warehouse operations or measured room dimensions. NYC DOB CO dataset: <https://data.cityofnewyork.us/d/pkdm-hqz6>. A certificate establishes permitted occupancy/use, **not** evidence of current occupation/tenant activity. This CO dataset is another DOB publication, so its independent-publication concordance is not independence from DOB as an agency. The absence of selected CO rows for another BIN cannot establish unoccupied property. Official OTI footprint schema: <https://data.cityofnewyork.us/d/5zhs-2jue>. DCP PLUTO: <https://data.cityofnewyork.us/d/64uk-42ks>.

## Exact software and evidence standards

`empire_os/property_claim_evidence_review.py` reads the current source report only after checking its matching provenance digest, bounded observation counts and the exact **16 Oct 2026** cohort identity. It re-queries exactly four official BIN identities, DCP lots, OTI footprint physical vs MapPLUTO identifiers and the separate DOB NOW CO source. It retains:
- Exact source dataset identifiers and selected-request URLs, selected-field source-response SHA-256, date/time of observation.
- For each pair, DOB job references and count, published values and **exact supported statement identifiers**; no free-form revenue/warehouse-operation inference.
- Explicit `not_proven` scopes for warehouse operation, occupancy, ownership, customer identity, physical construction start and revenue, plus a source-specific data-rights flag.
- Clear evidence grades: published official three-agency source references plus official DOF warehouse class; a DOB CO matching reference but unresolved OTI conflict; and wholly unresolved DOB/OTI mismatch.

`empire_os/property_claim_receipt_runtime.py` provides a strict **local receipt validator**. Every supported property statement must have matching approved statement ID, exact BIN/BBL, four expected dataset receipts, source-field response hashes, no commercial permission, an authenticated *local artifact checksum* (not official public signature), and observation freshness <=48h. **`supported_claim(...)` returns false for ANY unlisted statement type**, including `ACTIVE_WAREHOUSE_OPERATIONS`, `VERIFIED_REVENUE`, `OWNER_VERIFIED`, `BUYER_INTENT` or `CONTACT_APPROVED`. This is a narrowly scoped property claim contract, not a claim that every other EmpireOS subsystem yet complies.

`scripts/review_nyc_property_claim_receipts_readonly.py` is on demand. Without flags it prints the observed result and writes nothing. Explicit `--record-private` stores `runtime/data_brokerage/nyc_property_four_pair_claims_latest.json` and a separate private provenance receipt, both 0600, atomically with SHA-256 verification and bounded file sizes. No new database/department/agent/timer/source activation is created.

The existing Property Intelligence and Warehouse Intelligence projection exposes only source-validated **aggregate** counts/status; it does not promote a source-classified building into an operating company, lead/prospect, usable recipient, commercial agreement or recognized revenue. When receipts are absent, stale, modified, wrong-source or forged, its claimed evidence status is `NO_VERIFIED_PROPERTY_CLAIM_RECEIPTS`.

## Gap status and remaining work

- **Closed for this cohort:** traceable official-source warehouse-class identification and per-BIN/BBL source claim gating; two separate official DOB datasets' reference concordance for one Manhattan mismatch; correction that four industrial permit events correspond to two property reference pairs.
- **Still open:** current warehouse operating activity or tenants; industrial buyer demand and signed commercial terms; actual original DOB work scopes; adjudicating the Manhattan building-footprint lot discrepancy and Bronx adjacent-lot discrepancy; authoritative property owner identity; entitlement to redistribute proprietary derived/external information to customers; full ongoing snapshot/source-change monitoring; realized brokerage revenue.
- **Deployment state:** Code-only in existing canonical repository, data report private, DOB NOW scheduled source activation disabled, all customer/outbound/payment gates unchanged. No source record is a verified sales opportunity by itself.

**Rule for next projects:** retain the claim `statement_id`, its exact source reference (dataset/field), observed_at, digest/version, entity identity, scope boundary, contradicting sources and stale/invalid status. Report unknowns plainly. Use only claims whose contract validates from real observed evidence; never transform an inference into a verified fact without new source proof.
