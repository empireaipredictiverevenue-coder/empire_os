# Existing NewsJack / Last30Days handoff correction

16 November 2026. Original implementation branch:
`feature/jev-newsjack-traffic-20261018`.

The existing NewsJack CLI accepted raw signal packets and Last30Days agent
export schema 1.2. Production MediaOS currently exports
`empire.last30days.research_handoff.v1`, so its actual handoff could not enter
that CLI. The adapter now accepts this original source contract, without a
new collector, scheduler, agent, database or forecasting model.

## Implemented

- `signals_from_last30days_research_handoff` validates source permissions,
  two-hour handoff freshness, complete topic/reference counts, explicit topic
  selection, original publication instants, public HTTPS citations and rights.
- Preserves the 30-day research window and original evidence references;
  rejects malformed entries and deduplicates URLs/references within the topic.
- Stable source identities survive handoff refresh. Topic labels are explicitly
  research context, not invented article headlines. Operator-selected market
  and sector are research scope, not proven geography or buyer qualification.
- Existing CLI gains `--input-format last30days-handoff --topic ...`.
  Input files must be bounded regular files, not symlinks. Existing formats
  remain supported. No source file or queue is written.
- Original NewsJack seven-day reactive-news rule and Predictive 72-hour
  evidence rule remain unchanged. No conversion, traffic, profit, financial
  finality, calibration or publication authority is inferred.

## Live source verification

Read-only check at `2026-11-16T18:09:03.568279+00:00` against the actual
`/srv/empire_os/runtime/media_os/last30days/research_handoff_latest.json`:

- Original handoff generated `2026-11-16T17:41:55.800951+00:00`.
- SHA256 `b6d8324d4adca799d6d69d0e0ffde51c7a8b69ce95f2584dafcbe3b9315158ad`.
- 12 genuine public research references, three existing topics; all 12 mapped,
  no malformed entries or within-topic duplicates. Source bytes unchanged.
- AI agents: five mapped, three `RESEARCH_REVIEW`, two `HOLD_EVIDENCE`.
- AI sales avatars: six mapped, two `RESEARCH_REVIEW`, four `HOLD_EVIDENCE`.
- First-party revenue intelligence/attribution: one mapped, one
  `RESEARCH_REVIEW`; accepted by the original
  `review_existing_jev_newsjack_handoff` as
  `JEV_NEWSJACK_SOURCE_RESEARCH_REVIEWED`.
- Other two topics correctly held by the original Predictive adapter: none
  of their citations was within its stricter 72-hour research window. Their
  newer-than-seven-days citations are not automatically current-enough
  Predictive inputs.
- Market GB / sector AI was an explicit operator review scope only.
- This used original adapter implementations from their existing worktrees,
  not a deployed recurring integration. No registry forecasts or DB writes.

46 focused tests passed, including malformed/forged authority, incomplete
counts, future/stale sources, duplicate replay identity, preserved original
news gating, existing CLI compatibility and source-file immutability.
Test fixtures stayed isolated and are not customer activity.

## Reuse and activation boundary

The upstream reference is `https://github.com/elvisun/newsjack`, retrieved
separately at `928a82d8de3304e68a3a668aebf5be768464e9cd` into
`/home/ubuntu/empire_upstream_reviews/newsjack_20261116`.
Its existing Go detector already parses RSS/Atom feeds. Adding Feedparser
would duplicate that capability. No third-party libraries were installed.
Trafilatura, StatsForecast and monitoring libraries remain deferred until
an actual extraction/model/monitoring gap and genuine evaluation data exist.

No owner branch was merged, no production code or MediaOS configuration was
changed, no timer/service was added or restarted, and no publication occurred.
The existing NewsJack/JEV and Predictive source revisions still require the
original owner-controlled release reconciliation before recurring production
activation. Preserve those ownership and founder release gates; do not import
worktree paths into a production service or launch a second collector.

Manual read-only use from this original worktree:

```sh
/srv/empire_os/.venv/bin/python -B -m scripts.review_jev_newsjack_traffic \
  --input /srv/empire_os/runtime/media_os/last30days/research_handoff_latest.json \
  --input-format last30days-handoff \
  --topic 'first-party revenue intelligence and attribution' \
  --sector ai --market GB --as-of '<current-aware-UTC-timestamp>'
```

Read-only research success is not a revenue forecast or a deployment receipt.
Native recognized-revenue registration continues to require authenticated
tenant-bound commercial observations and the original model evidence gates.
