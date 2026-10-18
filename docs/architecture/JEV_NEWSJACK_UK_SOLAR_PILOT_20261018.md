# Empire AI — UK Solar, Current-Source Editorial Pilot

**Research snapshot:** Sunday 18 October 2026. No publication or customer outreach.

## Verified source and subject

Official GOV.UK Content API record:
https://www.gov.uk/government/speeches/building-an-energy-system-that-delivers-for-all

Title: *Building an energy system that delivers for all*.
First published: **14 October 2026**, 14:46:56 UTC (as reported by
the GOV.UK API). The speech discusses Great British Grid, community and
local energy, the Warm Homes Plan, and mentions solar in the context of
building upgrades. A speech is government policy direction, **not**
itself confirmation of a new solar subsidy, installer eligibility,
installation regulation, consumer demand or new paying buyer.

Existing first-party destinations directly inspected 18 October:
- https://empire-ai.co.uk/industries/solar — 200, original HTML,
  page title `Solar Installer Coverage & Lead Qualification | Empire AI`.
- https://empire-ai.co.uk/commercial — 200, original HTML, page title
  `AI Consultancy & Revenue Intelligence | Empire AI`.

The new command returned `EDITORIAL_RESEARCH_PREVIEW`, with these
two owned pages verified and no publishing authority.

## Original brief for SEO / Content OS review

**Working topic**: UK solar installer growth in late 2026: what the
14 October energy policy speech signals, and what still needs verification.

**Business audience**: UK solar installers evaluating service territory,
commercial opportunity, installation pipeline and lead qualification.

**Reader intent**: Understand whether policy direction changes measurable
local installer opportunity, permitting evidence, customer eligibility, or
operational barriers. Do not turn political rhetoric into a sales forecast.

**Draft outline — questions, not unsupported claims**:

1. What did the Energy Secretary actually say on 14 October, and how
   does that differ from rules or programmes already enacted?
2. How do solar installers verify live planning, permitted projects,
   properties, grid access, public funding and qualifying territories?
3. Which evidence can Empire AI help organise today, and what does
   it not know about an individual buyer, prospect or installation?
4. What should a prospective installer collect before a founder-led
   opportunity assessment?

**Existing relevant page**:
https://empire-ai.co.uk/industries/solar

**Existing commercial conversation page**:
https://empire-ai.co.uk/commercial

**Distribution candidates**: original linked explainer once approved,
a short LinkedIn summary with source citation, a factual YouTube explainer
only if genuinely new editorial value, and a useful newsletter question
summary. This document does not authorise any of those actions.

**Specific missing proof**: independent corroboration of relevant claims,
verified keyword/search demand for this topic, approval of original
editorial copy, verified conversion completion, publication receipt,
observed visitors and attributable qualified enquiries.

## Live GSC baseline

Official first-party Search Console reader on localhost:
`/v1/search/search-console/observations` for
**17 September–16 October 2026**, capped at 200 rows.

Returned **11 query+page rows**, **34 impressions**, **0 clicks**.
No rows in the returned sample pointed to `/industries/solar` or
`/industries/roofing`. This does **not** prove those pages have no
visitors, no demand or no indexing, only that the retrieved rows contain
none for those paths. Do not use this sample to project search volume.

## Exact command

```sh
cd /home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018
/srv/empire_os/.venv/bin/python -B -m scripts.review_jev_editorial_traffic \
  --govuk-url https://www.gov.uk/government/speeches/building-an-energy-system-that-delivers-for-all \
  --sector solar --market GB --as-of 2026-10-18T15:00:00+00:00 --include-items
```

**Current truth:** reviewed research opportunity and live destination.
**Not completed:** content approval, publication, traffic or revenue.
The source is official and dated, not a signal that somebody is ready to buy.

## 18 October shadow-model readback and next actions

The manual JEV-first review also ran against the existing live local
`empire-laya-shadow` sidecar with the same GOV.UK source. It returned
`content_brief` with **0.1233 classification confidence**, below the
0.75 review threshold. This number is neither traffic probability nor
commercial confidence and must not be promoted.

The review stayed `EDITORIAL_RESEARCH_PREVIEW` with
`low_confidence_shadow_decision`,
`independent_corroboration_required` and
`trusted_gsc_demand_observation_missing` as open research gaps.

**Best follow-up in the existing Search / Content departments:** find
actual UK solar installer questions by comparing current public
questions with first-party Search Console (currently no solar/roofing
page query rows in the returned 30-day sample). Research 2–3 dated,
independent primary observations before writing a new explainer.
Distinguish UK energy-policy direction from any newly enacted rules.
Once supported and editorially approved, use the existing live solar
and commercial pages to collect genuine enquiries. No new route or
duplicate content owner should be created by this bridge.

**Do not use this engineering release to publish autonomously.**
