# EmpireOS existing SEO/AEO/GEO system — recovery and Quora reuse audit

**Observed 21 October 2026 ~17:53–18:00 UTC.** Production: `/srv/empire_os`, branch `agent/data-cloud-wave4`, canonical DB **EmpireDB PostgreSQL**. Existing Search Intelligence engine, Search Fabric, publisher and Founder Console are canonical. No duplicate engine or agent, no Supabase, no paid search/traffic/editorial, no self-authorised publishes.

## Existing source and operating entrypoints

| Component | Location / command | Actual state |
|---|---|---|
| Provider selection, search and grounding | `empire_os/search_fabric/` (9 Python modules) | Source installed; Google SERP ranking/organic observations unverified |
| SEO/AEO/GEO intelligence products | `empire_os/search_intelligence/` (54 Python modules) | Source installed: GSC, technical, competitor, backlinks, citations, schemas, internal links, keyword/semantic, rank history, 404, attribution |
| Google Search Console | `http://127.0.0.1:8771/v1/search/summary` and `/v1/search/search-console/pages` | Service live; authenticated read API; site property `sc-domain:empire-ai.co.uk` configured |
| Consolidated department | `/v1/search/department/review`; `scripts/review_seo_department_integrated_20261018.py --review-only` | HTTP 200; `DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN`, mode OBSERVE |
| Founder console frontend | Existing `empire-founder-console.service` on `127.0.0.1:3001/department` | HTTP 200 private path; owner identity gate still **not independently verified** by the preflight |
| Search Command Centre application | `apps/search-command-centre` source/build | Exists; separate dedicated production unit unverified, don't create one |
| Daily organic observer | `empire-organic-search-recovery.timer` | Active; read-only |
| Roofing SEO-to-Ringba pulse | `empire-roofing-commercial-pulse.timer` | Active; read-only |
| Existing research | `docs/seo/`, `docs/marketing/`; 8 specialist desks, 9 research campaigns | Original drafts/reviews exist; owner/editorial publishing decisions still open |
| Roofing organic acquisition | `/roofing` plus existing `docs/commercial/LEAD_SMART_*ACQUISITION*` | Public main page HTTP 200; prospect inventory 20; call gate OFF |

## Live evidence, NOT performance promises

- GSC final returned **32 page rows** in the 7–20 Oct page reader. The integrated 7–19 Oct sample shows **64 impressions, zero clicks**; do not call that full sitewide performance or indexed/ranked status. Roofing `/roofing` specifically had **no reported page row** in the most recent commercial pulse.
- Search Fabric cache observed **1,875 files: 72 fresh 24h candidates, 1,799 stale**. Current local `/v1/search/summary` marks SERP source `INTEGRATION_PRESENT_OBSERVATION_UNVERIFIED`; Google ranks and external AI citations remain unverified.
- Integrated review open gates: original organic release/provenance; industry campaign approval; **30 historical GSC 404s for editorial review**; 2 semantic editorial candidates; independent SERP and AI-answer proof; real enquiries and paid settlements; owner publication.
- Two drafted homeowner articles exist at `apps/empire-public-site/src/app/roofing/installation-checklist/page.tsx` and `replacement-vs-repair/page.tsx`. They are **noindex drafts** and their public URLs returned **HTTP 405** on 21 Oct. Do not sitemap, publish or link them as live until exact owner/editorial review and guarded release.
- No proved original homeowner organic conversions, Lead Smart payable call acceptance or cash; do not count page views, Quora engagement, GSC rows, partner research or dial permits as revenue.

## Current read-only owner commands

```bash
cd /srv/empire_os
.venv/bin/python -B -m scripts.review_seo_department_integrated_20261018 --review-only
.venv/bin/python -B -m scripts.review_search_department_release_preflight_20261018 --read-only
.venv/bin/python -B -m scripts.review_lead_smart_acquisition_sourcing_20261021
.venv/bin/python -B -m scripts.review_lead_smart_commercial_pulse_20261020
```

## Reuse order for Lead Smart, without drifting

**SEO (primary):** inspect original GSC page evidence, target replacement/installation questions from genuine search, review the already-written homeowner guides, confirm original/safe page metadata, resolve 404/canonical editorial list, release useful pages only through existing founder-approved publisher. Search Fabric supplies *verified* search source observations or leaves ranking UNKNOWN.

**Quora (supporting organic distribution):** eight **question themes**, not verified live question URLs, are in `docs/seo/LEAD_SMART_QUORA_ANSWER_REVIEW_QUEUE_20261021.csv`. Existing Research/Editorial owner chooses actual current suitable questions and writes an original answer that stands on its own; credential/answer clearly discloses Empire AI affiliation where relevant. Quora says 1–3 substantive answers/week. Affiliate links forbidden; company site links only when directly helpful and the linked public educational page has passed editorial/publication approval. No automated posting or unsolicited private messages. Do not claim 8 published answers or Quora clicks.

**Local partners (optional):** reuse 20-person ORGANISATION (not homeowner) inventory in `docs/commercial/LEAD_SMART_CHICAGO_ORGANIC_REFERRAL_RESEARCH_20261021.csv`. Original publisher messages to Roofing Mate and Roofing Calculators were already sent; no duplicate sends. Check suppressions, conflicts, consent and source rights. Lead Smart currently permits `EMPIRE_FIRST_PARTY_ORGANIC`; an external publisher or Quora link must not be falsely labelled owned SEO or assumed approved buyer traffic.

**Commercial closeout:** website/guide → authentic attributed enquiry → source/ZIP/qualifying owner evidence → founder-approved call readiness → actual Ringba buyer leg → accepted final payable amount → actual settled wire/other accepted rail → EmpireDB economic receipt. Current Lead Smart call admission remains revoked and payment/revenue zero verified.

**Owner of unfinished integrations:** existing Search Intelligence/Search Fabric owner; original marketing_growth/SEO research and editorial owner; existing authenticated Founder Console owner; existing website/publisher owner; buyer sales and financial reviewer. Do not introduce a parallel crawler, search database, agent, publisher or timer.

**Reference worktrees:** `/home/ubuntu/empire_worktrees/seo_department_consolidation_20261018`, `/home/ubuntu/empire_worktrees/search_command_private_release_preflight_20261018`, `/home/ubuntu/empire_worktrees/openseo_gsc_keyword_bridge_20261016`, `/home/ubuntu/empire_worktrees/seo_director_microdirectories_20261014`; review their commits, don't merge stale tips indiscriminately. See `docs/seo/SEO_DEPARTMENT_CONSOLIDATION_20261018.md`, `docs/seo/FOUNDER_PRIVATE_SEO_DEPARTMENT_INCREMENTAL_RELEASE_20261018.md`, `docs/marketing/SEO_AEO_GEO_EDITORIAL_ACCEPTANCE_AND_GROWTH_001_HANDOFF_20261016.md`.

Quora policy sources: `https://business.quora.com/resources/writing-on-quora-as-a-business` and `https://help.quora.com/hc/en-us/articles/360055133711-What-is-Quora-s-policy-on-disclosing-affiliations-in-answers`.
