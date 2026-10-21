# Quora research channel — integrated into canonical Empire Search Intelligence
21 October 2026 · Source `empire_os/search_intelligence/quora_intelligence.py`

## Why this is an upgrade, not a new SEO bot
Quora is an **external answer/discussion research and earned-distribution channel**, not owned first-party search. This extension uses the existing Search Intelligence FastAPI router and the existing `SearchFabricSerpAdapter` instead of deploying a Quora scraper, credentials, publishing service, separate database or timers.

- **Curated topic input:** existing `docs/seo/LEAD_SMART_QUORA_ANSWER_REVIEW_QUEUE_20261021.csv` (eight roofing themes, review-only; no actual Quora links verified).
- **Search Fabric bridge:** `review_quora_serp_snapshot(seed_id, snapshot)` accepts the existing `SearchFabricSerpAdapter.snapshot(...)` data shape. Exact source query and matching provenance are required; stale/cached, failed, unavailable or off-domain results are not promoted. A deterministic row hash is only a traceable observation identifier, *not* a signature or direct Quora confirmation.
- **Evidence and intelligence:** only canonical HTTPS Quora question URL hypotheses are accepted. Topic/question review uses the existing `semantic_opportunity_review` intent and sector heuristics, with source refs and original observed time. Zero claims of buyer intent, rank, response, traffic, signed source, backlinks, accepted payable calls or settled revenue.
- **Existing private backend API:** `GET /v1/search/quora/review` provides review-only topics and discovery query plans; `POST /v1/search/quora/search-fabric/preview` validates bounded, untrusted candidate inputs without network, posting or writes. HTTP no-store and no-sniff on success. API depends on existing loopback-only service on `127.0.0.1:8771`; it must not be exposed publicly or through an unauthenticated Founder console.
- **Operational status:** source/API code and deterministic tests are the delivered increment; source/publishing ownership remains the existing marketing_growth, search and authenticated Founder teams. No Quora account or posting authority has been connected.

## Actual acquisition workflow
1. **SEO search intelligence** discovers roofing installation/replacement intent through verified GSC signals and Search Fabric's existing per-provider bounded queries. A Search Fabric result is an observed *search listing*, not authenticated Quora question content, organic search volume or current rank.
2. **Quora question candidates** are deduplicated and screened for title/URL/provenance/staleness, then sent to the **existing editorial owner**. A human checks the question is still live and community rules permit answering.
3. **Original expert answer** genuinely answers the homeowner's question on Quora, avoiding unverified local regulations, safety shortcuts or promises of covered areas, and stating Empire AI affiliation when relevant. No copied answers, AI-spam blasts, affiliate links or irrelevant website links.
4. **Owned educational pages** may be linked only if relevant, helpful, founder/editorial-approved and verifiably live/indexable. Existing roof-installation and repair-versus-replacement guides are staging/noindex and publicly HTTP 405; they are NOT approved public destinations yet.
5. **Attribution** keeps Quora external referrals separate from first-party owned search and partner traffic. Only an independently observed visit/call lifecycle can support conversions; no Quora view or hypothetical click is payable revenue.

## Original source policy
- Quora official affiliation policy: https://help.quora.com/hc/en-us/articles/360055133711-What-is-Quora-s-policy-on-disclosing-affiliations-in-answers
- Quora official abuse/bans policy: https://help.quora.com/hc/en-us/articles/360015712691-What-would-cause-my-account-to-be-banned/
- The platform forbids repeated irrelevant traffic-driving answers, coordinated inauthentic activity and deception. No automated Quora posting or direct messages are implemented.

## Work still needed to finish the SEO engine
- Authoritative actual Quora question-page verification and human-approved response publication; the present eight topics are research themes, **not observed live questions**.
- Connected Founder Console review UX with independently verified founder identity. Current private department interface exists but identity-gate review remains outstanding; do not inject route into the public site.
- Resolve independent SERP source freshness: Search Fabric cache currently dominated by stale data and Google rank positions unverified.
- SEO publication owner: review and publish the two existing homeowner guides with correct canonical, robots, sitemap and approved on-page legal/payout messaging; no byte drift in frozen buyer pages.
- Reconcile historical 404 editorial queue and original owned asset release provenance; measure actual first-party SEO/Quora referrals, then actual payables only after Lead Smart independent launch gating.

## Safe checks
```bash
cd /srv/empire_os
.venv/bin/python -m pytest -q tests/search_intelligence/test_quora_intelligence.py
curl -sS http://127.0.0.1:8771/v1/search/quora/review
```
For the second command, query only local loopback; output is editorial data not accounts or customer records. No database activation, outbound, publication, autonomous research spend or live phone calls is part of this release.
