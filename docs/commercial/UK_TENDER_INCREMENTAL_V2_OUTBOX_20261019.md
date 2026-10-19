# EmpireOS UK tender incremental V2 — 19 October 2026

Branch: feature/predictive-decision-control-20261018
Previous checkpoint: commit 9826b010

## Improvement

This release extends existing UK Find a Tender OCDS ingestion, not an
alternative database, crawler, model or scheduler.

- V2 starts with seven days of public-source update history but advances
  through contiguous, overlapping four-hour source partitions, each with at
  most 100 cursor pages. Five-minute overlap avoids skipping boundary updates.
- One source page is observed per explicit invocation. A frozen partition only
  advances its high watermark when the provider cursor is exhausted; it never
  implies the whole seven-day history is covered.
- The old V1 partial checkpoint remains untouched. V2 starts its own replay
  under runtime/source_intelligence/uk_tender_incremental_v2.json. Neither
  source state is written into production EmpireDB.
- Each updated tender payload is hashed (not copied) for change detection,
  so amendments to descriptions or requirements are detected even when the
  CPV classifications, deadline and status remain unchanged.
- A durable pending_sector_research outbox is included in the SAME atomic
  private checkpoint as the source cursor. It keeps only official source
  reference, hashed release/process identity, matched sector and the bounded
  source coverage flag.
- Only publisher-reported active tenders, with future deadline and narrow
  roofing, solar, HVAC or dental CPV matches, enter that outbox.
- An explicit internal dispatch option routes ONE pending packet to the
  EXISTING ASTRA DepartmentWorkQueue; only after successful enqueue does it
  acknowledge the private outbox record. A crash before acknowledgement
  retries the deterministic queue key, avoiding duplicate work. A failed
  queue write leaves pending evidence intact.
- No customer contact extraction, automatic commercial outreach, bidding,
  payment, CRM admission, forecasting or recognized revenue occurs.
- The existing Founder Console data-stream code now exposes pending research,
  the latest completed timestamp and remaining hours of lag, keeping
  a completed four-hour partition distinct from current source coverage.

## Source results in isolated feature worktree

The preserved V1 test contained 10 source release receipts from a partial
seven-day window. V2 independently replayed early seven-day backfill slices
as four-hour partitions. After six explicitly staged source pages, V2
contained 11 unique official release receipts in completed partitions. The
latest completed source window ended October 13 UTC, so the source was still
several days behind October 19. None of the scanned releases met the strict
sector-plus-active-deadline review filter; no tender-specific tasks were queued.

Existing broader ASTRA source-mining work was not reset or duplicated.
Source counts do not mean qualified buyers, won contracts or actual revenue.

## Safe operator commands

Working directory:
/home/ubuntu/empire_agents/predictive_decision_control_20261018

Read private checkpoint health without external calls:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --checkpoint-health

Read one official page without changing the checkpoint:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018

Stage one more official page to the isolated private V2 checkpoint:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --stage-private-checkpoint

Route one pending validated source review to existing ASTRA:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.scan_uk_tender_incremental_20261018 --enqueue-one-sector-review

Regression coverage: tests/test_uk_tender_incremental.py,
tests/test_public_source_sweep.py, tests/test_revenue_stream_mining.py,
tests/test_source_intelligence.py,
tests/test_source_intelligence_department_handoff_20261017.py,
tests/test_predictive_decision_control.py and tests/test_founder_dashboard.py.

## Remaining constraints

The V2 test does NOT activate source monitoring or a production feed.
Window history remains capped at 1200 receipts, in-flight pages at 100
and the pending research outbox at 100 packets. Exhausting these bounds
holds the source rather than silently skipping source records. The
existing Source Intelligence owner should coordinate safe historic
receipt retention, future scheduling and canonical source-to-Opportunity
Factory admission. None of these imply a customer paid us; real commercial
outcomes and custody-proven predictions remain a separate requirement.
