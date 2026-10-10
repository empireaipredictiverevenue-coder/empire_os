# TAM genuine-source acquisition connector — v1.1 evidence recovery

Date: 10 October 2026. Owned EmpireOS reader only, no automatic acquisition ledger writes.

## Actual production learning

Authorized RECC × existing solar first preview returned 40 valid GB member observations but **zero canonical matched observations**. The reader printed 869 entity/prospect relationship rows, **not** 869 unique businesses. Earlier TAM source-quality audit saw 83 distinct exact-sector solar entities with active links and zero acquisition ledger entries, within its bounded 630 candidate cohort. Do not equate a larger join count with the number of distinct companies.

The first matching release required exact normalized legal/business name before comparing website or phone, so trading-name differences were invisible. It also examined only the first 40 RECC members. Both are meaningful evidence-recall limitations, not proof of bad source data.

## Live source checks

The existing UK RECC adapter succeeded on its public directory. Public listing pages 0, 1, 2 returned **100 distinct member-page references each** and did not overlap; page 3 separately returned 100 member-page references. Page 2 member detail probe retrieved five genuine entries; four had an independently specified business website and five had a business phone. No names, phone numbers or source URLs were printed by these aggregate probes. This does not prove any of these entries matches our canonical entities.

RECC current member search is https://www.recc.org.uk/scheme/members and publishes member listings by technology. The directory is a third-party *public evidence source*, not a paid data vendor or database backend. Respect source availability and avoid raw directory resale or speculative company qualification.

## Enhanced existing connector

Updated in place, **not a new parallel app**:
- `empire_os/tam_source_acquisition_connector.py`
- `scripts/run_tam_source_acquisition_connector.py`
- `tests/test_tam_source_acquisition_connector.py`

Safeguards and improvements:

1. The bounded operator CLI accepts `--source-page` from 0 to 40 and `--page-count` up to **3**, RECC only. At most **40 genuine detail observations per page / 120 total**. It uses **one existing-entity read-only EmpireDB query** for the full sweep, no repeated DB acquisitions or scheduler. Non-RECC providers cannot use multiple pages. This is a bounded sample, not the whole RECC membership list.
2. Identity candidates are indexed by exact normalized name, independent business-owned website host and supported country-specific telephone format. GB +44 / 0044 / domestic zero prefix are normalised conservatively; unknown country/short phone is not evidence. Generic social/hosted domains do not count as independent business-site corroboration.
3. **STRONG_EVIDENCE_REVIEW** still requires exact name plus independently matching website or phone, unique canonical entity **and** unique linked prospect, without contradictory website evidence. It is a **review state**, never an auto-append approval.
4. Name variants with matching unique website/phone are surfaced as **NAME_VARIANT_..._REVIEW**, strictly manual. Multiple entities, multiple linked prospects, contradictory signals, reused website host or multiple source members matching one entity fail to ambiguous/conflict review; these do **not** authorize an acquisition INSERT.
5. Output aggregates now distinguish `target_relationship_rows_examined` from `unique_target_entities_examined`, report target counts with usable website or phone evidence, source observation counts with website or phone, page-by-page observation counts and name-variant reviews. Private 0600 JSON retains genuine URLs and proposed evidence, not stdout.
6. No tenant or CRM login authority, database write, source-URL fabrication, outreach, buyer intent, payments, revenue claim or timer. A later idempotent append-only database-attachment path requires separate transaction design, approved matching evidence and explicit founder approval.

## One more substantial, bounded, genuine-source preview

After code release is committed, an authorized operator can run:

```bash
cd /srv/empire_os && sudo -n bash scripts/run_tam_source_acquisition_connector.sh --observe --source recc_solar --sector solar --country GB --max-targets 250 --max-source 40 --source-page 1 --page-count 3
```

This inspects **three newly chosen listing pages (1, 2 and 3)** instead of repeating the initial page-0 sample. It may make up to 120 public detail requests; do not run repeatedly, spam the source or infer absence from a zero result. It emits only aggregate counts, including distinct canonical entities. It writes only a private local review file and makes **no EmpireDB changes**. If it fails, diagnose rather than retrying blindly.

The original phase-044 market-aware research snapshot remains valid regardless of the outcome of this separate connector preview.
