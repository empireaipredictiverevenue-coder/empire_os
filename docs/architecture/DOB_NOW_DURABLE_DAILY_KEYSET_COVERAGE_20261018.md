# EmpireOS — DOB NOW durable daily coverage & resumable keyset reader

**18 October 2026 | Canonical Data Intelligence / Permit / Property | Feature is GATED; no autonomous outward contact.**

## Previously proven baseline

Existing DOB NOW official sources:
- NYC DOB NOW Job Application Filings: `w9ak-ipjd`
- NYC DOB NOW Approved Permits: `rbx6-tga4`
- Daily event-date history remains distinct from source collection time and stage; legacy numeric BIS permit IDs remain in a separate source namespace.

Original bounded `current_event_sample()` (first ten offset pages) retrieved 400 initial permit rows but could not reliably resume after 400 or prove full-day coverage. Source counts on October 18 showed **444 rows** of new initial permits with **issued_date = 2026-10-16**. Distinct jobs are fewer because multiple work types share a job. Offset pagination can skip/duplicate when the source changes between pages.

## New source contract

The existing `nyc_dobnow.current_event_sample()` now optionally accepts `issued_day` and `after_source_row_id` using the official Socrata `:id` pseudo-column, with `$select=:id as source_row_id`, `$order=:id ASC`, and a bounded `:id > <validated-id>` query. It rejects unsafe date strings and cursor input. The original offset-mode API is backwards compatible for existing readers/tests.

`empire_os/dobnow_incremental.py` introduces *only a tiny private source progress receipt*, **not a database, new bus, or scheduler**:
- `runtime/acquisition/dobnow_daily_keyset_progress.json` — mode 0600, update under its own exclusive 0600 lock, 2MB limit, up to eight rolling UTC calendar days. Never stores consumer details or business contacts.
- At most ten 40-row official source pages in a single enabled cycle (400 maximum), retaining the exact last official source row ID, bounded SHA-256 response receipts, observed rows, and unique cross-checked job events.
- A date may be **INCOMPLETE_BOUNDED_KEYSET** with a staged private record set and a cursor. The next existing crawler cycle resumes, rather than re-downloading page one or claiming a finished feed.
- Only after the date partition ends does it independently fetch the **same-source filtered official COUNT**; the count must exactly match the total selected rows. A mismatched count holds the day and resets it to a from-start retry, with no signal inbox promotion.
- Only then are the bounded, contact-free official event signals committed to the **existing** `signal_inbox.enqueue_signals_batch()`. The checkpoint is marked complete **after** the signal-store batches succeed. A process crash before checkpoint can safely replay those jobs via existing fingerprint deduplication.
- A complete snapshot is `COMPLETE_DATE_PARTITION_AT_OBSERVATION_ONLY`, not proof the external government dataset will never change. Completed in-window dates are eligible for a full-source recheck after 24 hours. Outside the rolling window is not claimed as permanently monitored.
- The next-day selector gives priority to an already incomplete/held day, then the most recent unvisited date, then dates due for a recheck. This is bounded by the existing lookback interval and never enables an additional scheduled task.
- Invalid provider rows, malformed cursor, future dates, duplicate source IDs, wrong job/BBL/BIN mapping, backward event dates and incomplete source counts fail closed. No seller/customer/owner identity inferred.

The **already installed** `crawler_runner.run_source_safe()` routes `permits_dobnow` through that incremental review **only when the explicit existing flag `EMPIRE_DOBNOW_PERMIT_SOURCE_ENABLED=1` is present in its actual process environment**. When the flag is missing (current production status), no source read, progress write, customer creation or outreach occurs. A dry run previews the in-memory scan without writing the source state or inbox. Filtering requests that would break daily completeness are held instead of mutating only part of a day. All consumer-facing and financial gates remain OFF.

## Live-data proof from existing official sources (18 Oct)

Executed in a child process in an isolated temporary directory using an in-memory mock signal writer. Temporary flag state was explicitly local to the child process, **not installed in production services**.

| Actual source observation for 2026-10-16 | Verified result |
| --- | --- |
| Official initial-permit issued-day row count | **444** |
| First bounded keyset scan | 400 selected work-permit rows — INCOMPLETE, 285 distinct staged jobs, **no signal writer calls** |
| Resumed keyset scan | Remaining 44 selected permit rows |
| Reconciled source rows | **444 / 444** |
| Distinct two-DOB-dataset validated job references | **312** |
| Source receipt pages | **12** with SHA-256 evidence |
| Stored progress mode | 0600 |
| Source progression | COMPLETE_DATE_PARTITION_AT_OBSERVATION_ONLY |
| Canonical signal inbox/EmpireDB/CRM writes | **0** |
| Outbound, payments and recognized brokerage revenue | **0** |

These are official **published source rows and project-file references**, not verified physical site conditions, businesses, purchases, roofing jobs, construction start dates, insured losses or warehouse opportunities. The DOB source remains one agency represented by two published datasets; PLUTO provides a separate tax-lot reference but not a new independently verified building owner.

The source's `:id` ordering was verified live with successive `:id > cursor` queries. The source may mutate during a multi-page read despite a count reconciliation; this is a best-effort **observed source snapshot**, not a serializable source-side database transaction. Future improved source change-data-capture should compare per-row IDs/hashes and monitor corrections that move issuance dates across date partitions.

## Test and production promotion requirements

Focused tests: `tests/test_dobnow_daily_cursor_20261018.py`, existing `tests/test_dobnow_permit_signal_intake_20261018.py` and adjacent permit, worker, department, source and crawler regressions. Test unfinished-day resume, source count mismatch hold, corrupt state, write failure, no-live-commit preview, safe cursor syntax, source activation refusal, dedup and old BIS source isolation.

This is a **code release with live source-read QA**, *not enabling automatic schedule*. No service restart, source toggle, Supabase, database migration, paid endpoint, outreach, public product distribution, background automation or mass customer data import has been authorized.

**Next important gaps:** after an explicitly approved observed pilot, compare canonical 7-day date-by-date coverage, add per-row source mutation/change sweeps beyond the issuance-date horizon, and make independent building/parcel/industry join evidence available to Product/Market Intelligence. No commercial claims until verifiable fulfilment and contracts.
