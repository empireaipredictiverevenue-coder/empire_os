# National Storm Hub — one-shot NWS source refresh, OBSERVE only

2026-10-21: verified against actual `https://api.weather.gov/alerts/active?status=actual` response.

**Why:** the canonical `/srv/empire_os/runtime/storm_opportunity/latest.json` is from **2026-10-05**, and no active existing Storm Intelligence timer was confirmed. Starting the old `StormService` would instantiate the legacy `StormPredictor`, which contains optional Discord/Telegram side effects and callback hooks. We did **not** start it, install a timer, modify production runtime, activate notifications, create enquiries or make DB writes.

## Safe implementation

`scripts/observe_nsh_storm_source_20261021.py` reuses existing `StormService._canonical_event_row` and `build_storm_intelligence_runtime` without instantiating the legacy service, scheduler, LLM or outbound.

Run from this isolated worktree:

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/observe_nsh_storm_source_20261021.py \
 --read-only --fetch-live \
 --stage-dir /home/ubuntu/empire_releases/national_storm_hub/observations/nws_20261021_live
```

The explicit stage path is restricted to the dedicated observation release root; `--stage-dir` refuses an offline replay. `--source-file` is an offline test input and does **not** claim a fresh source retrieval. The script allows only canonical NWS warning types used by the existing Storm Predictor and caps event count and payload size. Unknown or malformed source data fails closed.

## Genuine live results, fetched 2026-10-21 14:58:27 UTC

- Official NWS feed last updated: 2026-10-21 14:55:18 UTC
- 331 official NWS alert source records reviewed
- 2 matching allowlisted warning types and 2 canonical source observations
- 0 rejected canonical observations
- 0 commercial candidates or payable enquiries
- No inferred damage, buyer demand or actual revenue
- OBSERVE authority, no payments, outbound, DB writes or notifications
- Staged file: `/home/ubuntu/empire_releases/national_storm_hub/observations/nws_20261021_live/runtime/storm_opportunity/latest.json`
- The canonical production runtime file remained untouched and dated October 5.

**Do not promote the staged file directly into production** without storm-owner review, exact code/source receipt validation and an explicit guarded change. The private founder page therefore still honestly reports `STALE` against the canonical runtime. This is only the fresh-source discovery and verification step, not the approved recurring production refresh.

## Tests and next gates

`tests/test_nsh_storm_source_observer_20261021.py` plus existing `tests/test_storm_service_grounded_runtime.py` and `tests/test_storm_intelligence_runtime.py` passed **31 tests**. To restore ongoing canonical freshness, review the existing Storm Service materialisation process with the storm owner and apply an OBSERVE-only job with source-freshness receipts and rollback only after approval. Never restore legacy notifier side effects.
