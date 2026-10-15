# Empire Data Exchange V14 — Temporal Signal Board and AGI Research Bridge

Date: 2026-10-15
Branch: `feature/empire-data-exchange-20261014`
Mode: **INTERNAL OBSERVE / NOT DEPLOYED / NOT DISTRIBUTABLE**

## Problem solved

Existing V1–V13 build independently validated official Planning Data
brownfield observations, historical changes, procurement metadata and OGL
field-by-field rights. But no single review surface connected all this
to a prioritised, repeatable evidence queue for the existing AGI/JEV
research council and eventual subscription product.

V14 assembles **verified-shape, time-ordered source changes** into an
internal signal board and embeds the bounded review tasks into the existing
Empire Data Exchange AGI bridge.

This is the next layer toward a stronger product than generic companies-
hiring/news-signal feeds: traceable source revisions, chronology, evidence
lineage, supersession tracking and legal distribution gates.

## Architecture / execution

```
Existing Planning Data bounded source snapshots (2–16)
        |
existing build_construction_history
  -> independently validated source snapshots
  -> integrity chain + comparable windows + real value transitions
        |
existing build_rights_preflight
  -> rebuilds source dossier and OGL field lineage
  -> rechecks procurement source as INDEPENDENT context, never site match
        |
NEW data_exchange_signal_board.build_signal_board
  -> individual field changes + source URLs + observed-before/after times
  -> superseded / still-reflected status against latest valid snapshot
  -> new/missing sample members are coverage changes, NOT site creation
  -> held comparisons cannot become positive source events
  -> OGL attribution and pending field-rights review are retained
  -> limited and sorted internal review queue, source/rights SHA-256
        |
NEW on-demand CLI preview_data_exchange_signal_board
        |
EXISTING review_data_exchange_agi
  -> receives at most 8 bounded source review tasks, all NON-EXECUTABLE
  -> preserves current cognitive packet, advisory research, model policy
```

Files:
- `empire_os/data_exchange_signal_board.py`
- `scripts/preview_data_exchange_signal_board.py`
- `tests/test_data_exchange_signal_board.py`
- bounded integration change: `empire_os/data_exchange_agi_bridge.py`

No duplicated data store, source fetcher, crawler, LLM runtime, AGI
controller, database, external API, email sender, timer or scheduler.

## Semantic correctness

- A Planning Data brownfield record is **not** a current permit,
  commissioned contractor, buyer, tender, construction start or business.
- An Empire observation timestamp is **not** a government record
  publication date or a timestamp of real-life project activity.
- A source field change has an event ID, evidence URL and bounded
  before/after values. Permissioned status is a recorded string, not
  independent assurance that work will proceed.
- Records appearing/disappearing from bounded samples are coverage
  changes, not new/deleted projects.
- A previously observed transition may have been superseded in the
  latest source; the board shows this explicitly.
- Find a Tender notices remain unlinked without a directly verified
  shared project identity. No supplier/contact details included.
- SOURCE hash chains detect accidental modifications only when later
  compared with independently preserved anchors; they are NOT official
  government signatures.
- OGL v3 is identified, but precise per-field personal-data/third-party
  exceptions, attribution and redistribution need independent clearance.
- No external customer publication, paid subscription activation, model
  training/promotion, verified conversion, outreach or revenue claim.

## Operator

When two or more independently captured snapshots are available:

```bash
cd /home/ubuntu/empire_worktrees/empire_data_exchange_20261014
PYTHONPATH=. /srv/empire_os/.venv/bin/python \
  -m scripts.preview_data_exchange_signal_board \
  --snapshots /path/to/older.json /path/to/newer.json \
  --limit 24
```

Optional `--procurement /path/to/previously-reviewed.json` provides
separate official Find a Tender context without merging projects. The
operator reads bounded JSON, emits JSON on stdout, and never fetches,
writes, exports, contacts or bills anyone.

## Production release proof still missing

1. Independently verified field-level OGL exception/privacy assessment.
2. Time-separated first-party observations in governed, durable EmpireDB
   custody with an independently anchored chain and retention policy.
3. Independent source identity spot checks and coverage/false-positive
   evaluation; accept that a sample can yield **zero** real changes.
4. Verified cross-source IDs before project joins.
5. Time-split real outcomes before any conversion/prediction metrics.
6. Scoped product entitlements, licence, tenant access and non-simulation
   release gauntlet; founder-approved deployment through existing services.

### Live source read: 15 October BST / 14 October 23:33 UTC

The bounded existing official probe fetched three actual UK Planning Data
brownfield records: 1722645, 1739516 and 1739547. All three source URLs
were retained, `rejected_counts={}`, and the rights gate correctly stayed
`RIGHTS_REVIEW_MISSING` / OBSERVE. Their public entry dates predate this
observation; this is **one** current snapshot, NOT proof of a new change,
construction start, fresh permit or buyer intent. No durable historical
snapshot pair was produced or inserted into EmpireDB.

Real buyer email to Results Agency has been sent and separately
attested in V13, but no buyer engagement, paid trial, project-intent
validation or Data Exchange revenue has yet been verified.

No production assets or contact workflows changed in V14.
