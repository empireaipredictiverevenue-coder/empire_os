# Empire AI — reuse NewsJack in the existing MediaOS and Marketing/PR stack

Date: 4 November 2026
Owner worktree: `/home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018`
Branch: `feature/jev-newsjack-traffic-20261018`
Mode: **DEVELOPMENT ONLY / RESEARCH PREVIEW / NO PRODUCTION ACTIVATION**

## Existing capabilities preserved

- Seven-day news freshness, evidence filters and JEV shadow review:
  `empire_os/jev_newsjack_traffic.py`.
- Official US Federal Register and GOV.UK metadata intake:
  `empire_os/jev_newsjack_official_sources.py`.
- last30days and first-party GSC Search Intelligence adapters:
  `empire_os/jev_newsjack_adapters.py`.
- Existing page/editorial handoffs and Marketing/PR attribution:
  `jev_newsjack_traffic_briefs.py`,
  `jev_newsjack_marketing_handoff.py`,
  `organic_campaign_touch.py`.

Upstream reference: https://github.com/elvisun/newsjack (MIT).
The upstream NewsJack package is **not installed or vendored**. Its
installer/CLI can auto-update and invoke additional services. Do not run
an unmanaged `curl | bash` installer, duplicate a news daemon, or
replace existing News/Research, JEV, Marketing, MediaOS or Smart CRM owners.

## New existing-system adapter

The pure `prepare_official_news_media_os_preview` function is added in
`jev_newsjack_adapters.py`. The existing official-news CLI gains the
`--media-os-review-preview` flag.

It constructs ordinary `MediaResearchPack` objects from eligible,
official-source **research-only** JEV reviews, with:

- Exact government host and evidence-ref restrictions.
- No candidates from `HOLD_EVIDENCE` or `NOT_RELEVANT`.
- US Federal Register day-only publication precision kept as day-only;
  GOV.UK timestamps preserved without invented publication hours.
- `rights_state=RESEARCH_REFERENCE_ONLY` and the existing source lineage.
- Empty claims, `claim_verification_required=True`, `script_ready=False`.
- No MediaOS queue writes, source scheduling, factual verification, scripts,
  indexing, journalist pitches, outreach, spending or revenue attribution.

The output is a **preview** for owner acceptance, never a new commercial
news feed, permission to redistribute source text, or an approved story.

## Freshness and verification evidence

A read-only live official Federal Register review of `solar` and `roofing`
on 4 November 2026 returned 0 qualifying candidates under the existing
filters, not proof that no relevant news exists.

Prior to this enhancement, the six relevant NewsJack test files passed
54 tests. The adapter adds offline safety/precision fixtures and a
non-network CLI test.

## Exact next release gates

1. Marketing/PR and Search owner examine a real dated source, article origin,
   independent corroboration and editorial standing.
2. Reconcile isolated NewsJack owner branch with the current production
   components; don't merge the dirty production root wholesale.
3. Test one corroborated review-only official story, then integrate with the
   **existing** MediaOS research intake after exact founder approval.
4. Preserve the current MediaOS timer, source-quality and independent
   claim-verification gates; keep outbound and publishing founder-approved.
5. Only attribute traffic and sales from real GSC/CRM evidence.

Status: **development integration verified, not production deployed**.

## 4 November — additional bounded live reconciliation

The public Federal Register API returned thousands of broad full-text
matches, but the original adapter fetched only a handful of newest records,
which were dominated by combined filing notices. The existing adapter now
scans at most 50 records and returns at most the caller's original small
result cap. Topic matching for multiword concepts requires the actual phrase
(or the exact AI abbreviation for artificial intelligence). Duplicate
government document IDs are discarded. These are **source-relevance
improvements only**, not independent claim verification.

The new pure `reconcile_official_news_media_os_intake` function consumes
the *existing current* MediaOS research JSON envelope, compares proposed
official news packs against the existing IDs and source URLs, holds unsafe
or forged news metadata, and returns a claimless, no-write reconciliation
report. It does **not** import or overwrite this old branch's
`empire_os/media_research_bridge.py`; that file differs from the newer
production bridge and must remain under its original owner.

Manual CLI support for this current-snapshot comparison:

```sh
cd /home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018
PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -B -m \
  scripts.review_jev_official_news_sources \
  --federal-register-term solar --sector solar \
  --as-of 2026-11-04T14:17:00+00:00 --limit 8 \
  --media-os-review-preview \
  --media-os-current-input \
    /srv/empire_os/runtime/media_os/input/research_pack_candidates.json
```

A real 4 November read-only canary identified one sector-specific solar
filing from 8 October, but the current seven-day NewsJack gate held it as
stale. The live artificial-intelligence canary found no sufficiently
specific headline within the bounded scan. Both returned **zero new
research packets**; existing MediaOS had five candidates, unchanged.

The current MediaOS candidate input SHA256 was
`595a645ee210c5cb05f8c05ef3205b743eb5fae9057c952457f3810bc056d013`
before and after this specific read-only canary. This is a point-in-time
receipt: the active MediaOS timer may rewrite the input normally later.

The next owner task remains to obtain a genuinely fresh, independently
reviewed official story, then approve a controlled same-owner intake
of its claimless pack. Do not auto-publish or claim traffic/revenue.
