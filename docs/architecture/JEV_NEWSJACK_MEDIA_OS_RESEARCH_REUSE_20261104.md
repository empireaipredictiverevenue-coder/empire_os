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
