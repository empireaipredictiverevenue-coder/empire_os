# Empire Predictive Revenue — UK Public Tender Incremental Pilot

18 October 2026. Owner: Existing Source Intelligence / Predictive Revenue.
Feature branch: `feature/predictive-decision-control-20261018`.

## Why

Wave 2 implemented fixed-size public OCDS observation only. It couldn't
follow subsequent source pages, recognise a changed tender release, maintain
a durable high watermark or recover from a failed run. Treating its five
sample records as all procurement activity would be incorrect.

This additive wave extends `empire_os/uk_public_tender_observer.py` and
builds `empire_os/uk_tender_incremental.py` **without replacing that adapter,
Source Intelligence, the department queue or EmpireDB**.

## Canonical official API

[Public UK OCDS release endpoint](https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages).

The public API accepts:
- `limit` (1–100, pilot hardwired to 5);
- `stages=tender`;
- `updatedFrom` / `updatedTo` date-time filters;
- source-issued `cursor` for the next page.

The provider's `links.next` URL is **parsed, not fetched directly**.
The code only permits a token conforming to the documented character and
length limits and the same official HTTPS host, exact endpoint path, page
size, stage and frozen update window. The next URL is reconstructed by
the client. Any mismatched query, extra field, redirect or unexpected host
fails closed.

The unrelated authenticated notice-submission API is NOT used.

## Durable source-window algorithm

1. Read and validate previous bounded checkpoint (or start an empty one).
2. First explicit run: freeze an initial **7-day backfill** ending 5 minutes
   before the observation time. Later runs overlap last completed endpoint
   by 5 minutes, so late updates are rechecked.
3. Download at most **one page per explicit invocation**, max 5 OCDS
   releases, 1 MB, 8-second timeout.
4. Validate source publisher/licence, unique release IDs, optional
   next cursor, narrow CPV code categories and official source links.
5. Keep only hashed release/process IDs and a deterministic digest of
   published status, date, CPV and deadline; do not persist bidder/buyer
   contacts, vendor names, free text, document contents, contract amounts
   or precise personal addresses.
6. Identify NEW procurement process, NEW release in an existing process,
   SEMANTICALLY CHANGED release and IDENTICAL REPLAY. A new release
   (amendment) does not imply a distinct new customer.
7. Persist only in-flight cursor and bounded source digest set. A crash
   before an atomic checkpoint replace repeats the page safely.
8. A completed high watermark is recorded **only when an official page has
   no valid next cursor AND is not suspiciously full**. A full page without
   pagination is held. A partial or inconsistent window cannot be promoted.
9. Enforce 100-page/window and 1200-entry history budgets. A crowded
   window is an explicit internal research hold, not permission to silently
   skip source records. A future version can split/repartition large
   windows after an owner-approved migration.
10. Only an explicit option writes a chmod 0600, lock-protected, atomically
    replaced JSON progress file in THIS ISOLATED FEATURE WORKTREE:
    `runtime/source_intelligence/uk_tender_incremental_v1.json`.
    Default preview reads a single page but writes no checkpoint.

No systemd timer, new live DB table, new hosted data platform, new sender,
revenue recognition, buyer acceptance or automatic tender bid is enabled.

### Research handoff

For each changed/added release with *official narrow sector CPV* **and**
publisher-reported active status **and** a future tender deadline, a
`sector_research` packet can be prepared for a human specialist. Packets
reference the official process, hashed stable identity and sector.
They expressly require independent notice/eligibility recheck, prohibit
automatic CRM admission, and cannot create a buyer, contract or payment.

No actual ASTRA source research job is dispatched automatically by the
incremental scanner. Existing specialist source-review work has already
been queued by the earlier wave. We must validate relevance and terms
before entering the approved commercial process.

## Live bounded feature-worktree checkpoint (18 October)

- An initial review-only 24-hour observation yielded zero source rows,
  correctly demonstrating that short windows can be empty.
- A corrected **7-day initial backfill**, read-only preview, found
  five active published releases in the first page, with a next cursor.
- Founder-directed private, isolated feature-worktree staging then consumed
  two official 5-record pages, keeping **10 unique hashed release receipts**
  under strict private filesystem permissions.
- **State: PARTIAL_BACKFILL**. Two pages consumed. Cursor remains.
  `last_complete_window_end = null`. Full-window evidence coverage has
  NOT been asserted; no qualified paying buyer or verified revenue claimed.
- The production `/srv/empire_os` status remains **NOT_ACTIVATED**;
  no checkpoint, service, scheduled fetch or economic mutation was applied.
- The existing read-only source-discovery Founder Console API can show
  checkpoint health (partial pages, receipt count, latest completed
  watermark) without disclosing source cursor or personal data. Actual
  Founder Console is not deployed from this branch.

## Manual commands

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

# One source page, read-only preview; never claim a persisted watermark.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.scan_uk_tender_incremental_20261018

# Explicit private feature-worktree staging of ONE further source page.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.scan_uk_tender_incremental_20261018 \
  --stage-private-checkpoint

# Offline regression only; no external GET.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_uk_tender_incremental.py \
  tests/test_public_source_sweep.py \
  tests/test_revenue_stream_mining.py
```

On rate limiting, source schema mismatch, corrupt checkpoint, unsafe symlink,
cursor drift or missing page, fail closed and preserve last committed page.
No automatic retries or unlimited backfill loops.

## Remaining before future scheduled deployment

- Independent owner review of original source terms, paging and case
  coverage in the presence of amendments, deletion, and provider outages.
- A bounded, owner-approved source cycle integrated with the **existing**
  Source Intelligence and Sensor Mesh timers, not a duplicate scheduler.
- Define retention/pruning based on verified source-watermark scope; until
  then the 1200-entry bound deliberately fails closed.
- Source-classification QA for real solar, roofing, HVAC/dental public CPV
  patterns with original OCDS notice verification.
- Evidence-to-Opportunity Factory bridge only after validated organisation,
  terms, true buyer demand and non-personal-data source permissions.
- Original prospective prediction custody and actual verified outcomes before
  calibration or revenue claims.

Source counts are **source record receipts** and should never be added to
existing permit records, inferred buyer leads or claimed realised revenue.
