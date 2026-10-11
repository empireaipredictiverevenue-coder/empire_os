# EmpireOS — Opportunity Daily Results evidence integration, 11 October 2026

**Canonical checklist ID:** `check_6b120a710955f378`, line 190 of `docs/MASTER_REMAINING_CHECKLIST.md`.
**Task:** “Daily Results: what AI found, researched, advanced, blocked, proved and learned.”
**State:** code and existing API compatibility tested in isolation, NOT YET DEPLOYED.
**Branch:** `feature/daily-results-opportunity-evidence-20261011`, based on `d4599b40`.

## Reuse production contracts

The existing `empire_os.daily_results.build_daily_results` already writes the canonical `runtime/daily_results/latest.json` and per-day history via `scripts/build_daily_results.py`, and the existing `/v1/founder-daily-results/latest` API reads that artifact. Existing snapshots are available for dates from September through 11 October. We do **not** create another founder report, endpoint, timer, agent, database or delivery service.

The missing element was a time-scoped Opportunity Radar breakdown. Add `opportunity_daily` to the existing report envelope, without changing original fields, and keep the same existing founder API.

## Semantics and fail-closed truth

`found`: opportunity candidates observed in the **last successfully completed, same-Europe/London-date OBSERVE cycle**. These are not new business leads, new buyers, acquisitions or attributed revenue. `new_identity_count_latest_cycle` remains null until the same cycle's source-bound, active Opportunity Router history is available.

`researched`: number of candidate reviews and newly collected public-research observations from the latest successful cycle. These are observed research counts, never verified willingness to pay.

`advanced`: derived lifecycle stage transitions from same-cycle router/history output, only when such a source actually exists. Stage-count snapshots may show QUALIFY but **do not** constitute independently verified commercial progression or payable outcomes.

`blocked`: current cycle's Factory blocked-candidate count, not newly failed sales or permanently lost leads.

`proved`: verified commercial outcomes **today** remain null / `CANONICAL_OUTCOME_EVENT_FEED_NOT_BOUND` until an actual independent canonical outcome-event feed (payment, fulfilment and recognised revenue) is bound to the report. Never infer a nonzero proof from Radar stages or a model prediction.

`learned`: verify a fresh same-day Cortex learning snapshot, no synthetic commercial labels, forecast-labelled wins or model-weight mutation, before reporting verified customer learning packet counts. Stale Cortex source means unknown, not a zero or an assumed stable model.

Each report explicitly states `LATEST_COMPLETED_CYCLE_ONLY_NOT_DAILY_TOTAL`, so repeated cycles are not falsely summed into daily totals. It returns `NO_COMPLETE_ON_DATE_OPPORTUNITY_LOOP` if latest loop is stale/failed/unsafe or crosses a London local calendar-day boundary. All numeric observations are strict nonnegative integers; missing/negative/boolean/strings do not become valid counts.

## Read-only verification on actual production snapshots

The isolated `build_daily_results(/srv/empire_os)` returned for the **latest available 11 October cycle at verification**:

- 18 existing Radar opportunity candidates;
- 5 research candidates processed and 4 new public-research observations in that cycle;
- 18 Factory candidates blocked; current derived lifecycle stages all QUALIFY;
- new-history identities and actual stage transitions **unknown** because the historical router feature is not deployed;
- independently proved commercial outcomes **unknown**, not zero;
- current verified learning packet count **unknown** because the existing Cortex snapshot was dated 22 September;
- no payment, commercial promotion or execution authority inferred.

SHA256 checks of the underlying Opportunity Loop, Evidence Router, Cortex snapshot and existing Daily Results output were unchanged after the dry run.

## Tests and release

- Focused original/new Daily Results and revenue tests: **54 passed**.
- Wider daily-results → Founder API → Radar/Factory/Opportunity History → Astra/Cortex/regression suite: **281 passed**; one upstream Starlette/anyio deprecation warning, no failures.
- New test asserts the original Founder Daily Results API transparently returns the `opportunity_daily` section without any new endpoint or write.

This is **code complete, not live** until the owner merges and reruns the existing daily-result materialiser and verifies the section from the founder API. The master task stays open until production readback. No new reports were written into live `runtime/daily_results`.

Keep the separate Opportunity History `2b0b9544` and Astra validated workstream ranking `d4599b40` ahead of this change in the integrated release chain. Do not activate paid traffic, caller routes, mail sends, migrations, funds or model training through this projection.
