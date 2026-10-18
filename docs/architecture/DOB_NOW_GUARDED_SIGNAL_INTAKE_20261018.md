# EmpireOS DOB NOW permit-source intake — gated, tested, distinct from BIS

**18 October 2026 | Existing Permit Intelligence / Source Intelligence / Property / Data Brokerage | £0 additional spend**

## Milestone accomplished

Existing `empire_os/lead_sources` registry now includes `permits_dobnow` as an **explicitly gated** real source. It is **not live scheduled** unless `EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED=1` is explicitly configured. Absence, `false` or `0` are inert. It reuses the current 6-hour crawler, signal inbox, Permit Intelligence, source reviewer, existing department queue and current Event Revision history. No Supabase, DB tables, services, agents, timers, payment, customer campaign, automatic outbound or external distribution were created.

Two **separate official NYC Department of Buildings datasets** are required for each event:
- `w9ak-ipjd`: DOB NOW Build Job Application Filings (`filing_date`, `first_permit_date`).
- `rbx6-tga4`: DOB NOW Build Approved Permits (`issued_date`, `filing_reason`, `work_type`, `permit_status`).

A candidate must have matching validated alphanumeric `job_filing_number`, actual filing/first-permit/issuance dates, matching official borough/BIN/BBL, initial permit type and issued status. Original application date remains distinct from issuance. Multiple work permits under one job are **collapsed to one project-event signal**, retaining distinct work types and the number of underlying selected permit rows; conflicting building references fail closed. Neither source dataset independently verifies ownership or construction underway.

**No personal columns are even requested from the APIs**. The resulting evidence contains only source references, dates, work-type tags and geography codes; no street addresses, natural-person names, email addresses, phone numbers, claimant/policyholder data, buyer capacity or interested purchaser claims.

The existing `candidate_quality` classifies `permits_nyc_dobnow` as a **signal**, which can enter the existing private `signal_inbox` but cannot produce canonical prospects or sale-ready recipients. The `signal_resolver` explicitly defers it. The existing Permit/Property projection sees the source with a real `job_filing_number` reference. The Permit team classifier uses DOB NOW's **own validated official source page and alphanumeric ID**, never fabricates a legacy `a810-biswebportal` numeric job URL, and exposes bounded sanctioned event-status intelligence without contacts.

The existing signal-inbox lock/atomic write retains a stable source fingerprint for each DOB NOW job. Revisits do not duplicate records. Real sanitized source-field changes append bounded revision history; rewound issuance/filing dates are refused. Existing unrelated sources are unchanged.

## Query limits and operational honesty

- API timeouts 15s per call, two official source GETs per page, at most 40 rows per page, **10 pages / 400 raw work-permit rows maximum** per enabled crawl. No pagination beyond that bound or third-party enrichment.
- `sample_may_be_incomplete=true` whenever a page hits its 40-row cap. Cross-check mismatches are held, not called current/issued projects. 400 permit rows is **NOT comprehensive coverage** of NYC's source dataset or all physical jobs. Long-lived pagination/watermark reconciliation and full replay still need source-owner design, rather than claiming the initial bounded pilot solves completeness.
- The same official job may occur across pages. A per-run seen set and the permanent signal fingerprint both prevent repeat materialization.
- Original selected-field query-response SHA-256 and source date truth remain independently inspectable in the existing private research artefacts; the live gated reader itself does not persist third-party raw source responses.
- No request from this read-only tool sends mail, creates opportunities, accesses customer CRM, changes funds, accesses claims, or assumes entitlement to resell entire official datasets. Source attribution and downstream source-specific rights review remain required for distribution.

## Verified live research and isolated replay (18 Oct)

A direct, unscheduled read-only execution against both actual official NYC datasets yielded:
- 40 sampled source initial-permit rows.
- **36 distinct jobs with successful exact two-DOB-source current first-issuance checks**.
- Three additional work-permit rows collapsed under duplicate job IDs within the qualifying subset.
- All 36 had first permits issued on **16 October 2026**; original filings were earlier, not 36 new project applications.
- In a temporary local copy of the existing `signal_inbox`, the first pass created 36 records; the second identical pass was 36 matches, leaving 36 total. The exact existing Permit Intelligence/Source Intelligence modules classified **36** current official issuance events and kept source-specific buyer/company identity unverified.
- **Zero canonical EmpireDB writes, live acquisitions, consumer records, emails, eligible buyers, verified payments or realised revenue.**
- Tests cover sources/URLs, event date mismatch, duplicate permits, duplicate input, source regressions, business-source non-promotion, source revision, old BIS namespace isolation, pagination bounds, enabled-flag negative cases, normal crawler/worker regressions.

## Existing-file ownership and gates

Integration files:
- `empire_os/lead_sources/nyc_dobnow.py` — bounded read-only source contract and existing-source registration
- `empire_os/dobnow_event_revision.py` — bounded official event-only update metadata
- `empire_os/lead_sources/__init__.py`, `candidate_quality.py`, `signal_inbox.py`, `permit_intelligence_runtime.py`, `permit_project_intelligence.py`, `signal_resolver.py` — surgical integration into **existing** infrastructure
- `tests/test_dobnow_permit_signal_intake_20261018.py` — source-specific permanent regression

**Deployment default:** GATED / disabled. Do not set `EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED=1` in production until the founder authorises source activation and service owner confirms monitored crawler budget/coverage, source usage, release/rollback. Simply landing code is not enabling the reader.

**Read-only direct inspection example**, with NO enable flag and NO writes to EmpireDB:
```bash
cd /srv/empire_os
./.venv/bin/python -B - <<'PY'
from empire_os.lead_sources.nyc_dobnow import current_event_sample
r = current_event_sample()
print({"review_status":r["status"],"sample_source_rows":r["query_rows"],
       "crosschecked_jobs":len(r["events"]),
       "incomplete_coverage":r["sample_may_be_incomplete"]})
PY
```

**Next data efficacy priorities:** incremental high-watermark paging within existing crawler/source queues; missing/unmatched official records as explicit data QA; actual time-aligned DCP property context at building level; UK planning and warehouse official-source equivalents; legal firm-side intelligence; historic Common Crawl treated as archived. Keep every subsequent success criterion sourced, tested, bounded and no outbound.
