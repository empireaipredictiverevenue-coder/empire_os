# Empire AI — Video-Inspired Commercial Framework (Isolated Technical Handoff)

**Date:** 19 October 2026
**Owner worktree:** `/home/ubuntu/empire_worktrees/video_commercial_framework_20261019`
**Branch:** `feature/video-commercial-framework-20261019`
**Source baseline:** `41e0f803`
**Production status:** NOT DEPLOYED. No canonical repository, database, public website, CRM, outbound, payment, agent timer, or model weights changed.

## Context and evidence

Input inspiration: Dan Martell, "If I Wanted to Make My First $100K/Month, I'd Do This", YouTube ID `xj5gZq159lM`.
The canonical first-party YouTube metadata reader confirmed the title and author. It **did not** retrieve a transcript or watch the video. External full-video/transcript access was blocked by unavailable vidIQ credits. The six commercial principles here are our proposed strategic adaptation, **not a word-for-word transcript**.

## What was actually built

New module: `empire_os/video_commercial_growth_framework.py`
New read-only CLI: `scripts/review_video_commercial_growth_framework_20261019.py`
Tests: `tests/test_video_commercial_growth_framework.py`

Pure orchestration of existing verified packet formats:
- `empire.predictive-revenue.commercial-offer-book.v2` from existing `empire_os/commercial_offer_book.py`.
- `empire.founder_commercial_funnel.v1` from existing `empire_os/commercial_funnel.py`.
- Research observation lists or the existing signal-ID-keyed `runtime/revenue_actors/community_intent_normalized.json`.
- Exact canonical prospect-ID join only. Never infer a buyer identity from company name, domain, community author, source URL or similarity.
- Deduplicate research signals and preserve unmatched signals in an explicit review queue.
- Produce prioritized read-only next actions, unverified pain hypotheses, approved offer price **basis** where present, and explicit outreach/payment blockers.
- Surface aggregate funnel revenue **as supplied**, not independently verified or attributed to reviewed prospects.
- Detect stale, unknown, invalid, or future-dated offer/funnel snapshots (72-hour review threshold). Never claim current readiness from stale source data.

All outputs are `OBSERVE_ONLY`. No prospect created, no email sent, no pricing changed, no CRM or database updated, no money moved, no website modified, no live automation enabled.

## Existing producer and owner boundaries

| Existing owner | Read contract only | Do not modify |
| --- | --- | --- |
| Commercial catalog / offer book | `runtime/predictive_revenue/commercial_offer_book/latest.json` | `empire_os/commercial_offer_book.py` or its builder |
| Funnel / attribution | `runtime/commercial_funnel/latest.json` | `empire_os/commercial_funnel.py`, payment/recognition |
| Community Intent | `runtime/revenue_actors/community_intent_normalized.json` | Community/Reddit source and revenue actor producers |
| Buyer Scout | canonical IDs **only** when observed | scout identity authority, suppression, contact routing |
| Sales Director / CRM | future governed review consumer | inbox, send, terms, lead state, closer decisions |
| Revenue OS learning | future validated outcome consumer | model training or learning weight mutation |

Keep this implementation isolated unless the relevant owner explicitly accepts a schema-level interface. Do **not** copy the file into `/srv/empire_os` directly.

## Real stored packet dry run (read-only)

Runtime snapshots inspected on 19 Oct 2026:
- Offer book: 246 targets, **generated 2026-09-30**.
- Commercial funnel: **generated 2026-09-22**.
- Community Intent: 9 unlinked research signals.

Result:
- **235 targets** → `RESOLVE_CANONICAL_PROSPECT_ID`.
- **11 targets** → `VERIFY_PRODUCT_TERMS_AND_FULFILLMENT`.
- **0 community signals** could safely be linked to existing canonical prospect IDs.
- **9** retained as unlinked research.
- Both offer and funnel snapshots classified **STALE**; refresh before making operational revenue claims or contacting buyers.

These are **historical packet counts**, **not current qualified leads**, verified buyer capacity, live inventory, or recognized revenue.

## Tests and verification

Command:
```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_video_commercial_growth_framework.py \
  tests/test_commercial_offer_book.py \
  tests/test_gtm_offer_strategy.py \
  tests/test_commercial_funnel.py \
  tests/test_revenue_os_learning.py
```

**38 passed** (one external dependency deprecation warning). Contract tests cover identity collision, duplicate signals, evidence links, community authors, stale snapshots, offer catalog gates, contact authority, no invented revenue, and aggregate-only economic evidence.

Read-only CLI (prints JSON to stdout, no file or DB writes):
```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_video_commercial_growth_framework_20261019 \
  --read-only \
  --observations-file /srv/empire_os/runtime/revenue_actors/community_intent_normalized.json \
  --offer-book-file /srv/empire_os/runtime/predictive_revenue/commercial_offer_book/latest.json \
  --funnel-file /srv/empire_os/runtime/commercial_funnel/latest.json
```

This is an informational run. Do not mistake its candidate output for live commercial authorization.

## Recommended next steps

1. **Existing source owners**: refresh offer-book and commercial funnel from approved canonical producers and inspect provenance; do not manually overwrite a snapshot.
2. **Buyer Scout / identity owner**: investigate the 235 missing canonical IDs, maintaining dedup, provenance, and suppression. Do not map names/domains or social authors to identities by guesswork.
3. **Commercial catalog owner**: address the 11 product/terms blockers with verified pricing, lawful deliverability, and sale conditions.
4. **Sales Director owner**: add a read-only consumer for the new review schema; require fresh inbox/thread and founder approval for any live outbound.
5. **Learning owner**: design a separately approved connector to verified payments, fulfillment, margin and consented conversion outcomes; no automatic model updates from research hypotheses.
6. **Founder dashboard**: present freshness, unlinked signals, canonical-ID gaps, ready offers and verified commercial outcomes as separate counts.

The goal is to turn research → *verified* offer → real conversation → fulfilment → recognized revenue into a measurable loop without duplicate agents, fabricated buyers or autonomous commercial authority.

**Release gate:** relevant owner review + renewed source data + explicit founder approval + production QA. This worktree has NONE of that authority.
