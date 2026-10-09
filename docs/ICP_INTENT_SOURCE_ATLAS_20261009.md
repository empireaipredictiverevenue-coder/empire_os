# EmpireOS ICP Community Intent — 9 October 2026

## Revenue objective

Find where businesses and potential qualified-call buyers discuss concrete,
costly problems; connect public evidence to EmpireOS products and existing
company/Gmail relationships only when identity and commercial terms are proven.

**The loop:** target-market surface → permitted public observation →
operator-versus-seller classification → pain taxonomy →
candidate Empire AI solution → independent company identity →
existing CRM/Gmail thread → founder approval → verified offer/revenue.

These are **hypotheses and research signals**, not buying intent or authorisation.

## Source atlas

Authoritative structured catalog: `empire_os/icp_intent_source_atlas.py`.

Revenue-first automatic **public Reddit RSS** rotation (one subreddit query per
existing 15-minute collector cycle):

| ICP | Public source | Problem / Empire opportunity |
|---|---|---|
| Roofing contractor | r/RoofingSales, r/Roofing | CAC, bad appointments, SEO; demand intelligence + conversion |
| Lead publisher/buyer | r/LeadGenMarketplace | Qualified-call demand, coverage, buying requirements |
| HVAC | r/hvacpeople | Installation leads, agency spend, quote conversion |
| Legal practices | r/LawFirm | Client acquisition, intake, referral dependency |
| UK SMB | r/smallbusinessuk | B2B demand and longer conversion cycles |
| General SMB | r/smallbusiness, r/Entrepreneur | Lead generation, manual follow-ups, growth |
| Solar | r/Solarbusiness | Qualified appointments and lead cost |
| Agencies | r/agency, r/localseo | Churn, harder closes, reporting, GEO/AI search |

The collector also retains core cross-industry public queries and supports
fresh LinkedIn **only when independent search retrieval succeeds**. The
existing search circuit breaker is used; stale cached posts are not reissued
as today's intent.

**Manual research only**:
- Alignable small-business lead-generation and marketing groups:
  https://www.alignable.com/groups/small-business-lead-generation
  https://www.alignable.com/groups/marketing-for-the-small-business
  (group rules restrict solicitation; no automatic platform collection)
- affLIFT Pay Per Call forum:
  https://afflift.com/f/forums/pay-per-call.51/
  (some content requires membership; no bypass or private scraping)

Sources were checked against public community pages on 9 October 2026;
public presence is not authorisation for promotional contact.

## Qualification contract

`empire_os/icp_intent_relevance.py` labels observations:
- **EXPLICIT_REQUEST_UNVERIFIED** — a written request for a solution; poster and
  buyer identity still require independent verification.
- **OPERATOR_PROBLEM_SELF_REPORTED** — first-person business problems, no
  identity or verified spend.
- **SELLER_PITCH** — agencies and other suppliers advertising their services;
  do not inflate purchasing intent.
- **CONTENT_OR_ADVICE** and **UNATTRIBUTED_DISCUSSION** — research and market
  insights only.

Pain themes map to the already-existing `pain_solution_engine.SOLUTION_MAP`.
This is a proposed product fit, not approval, price quotation, deliverability,
buyer budget or binding terms.

Social-to-company matches require an explicit external business URL and are
only potential citations. The output never grants contact authority and
cannot activate call routing, paid traffic, bulk social DMs or email.

## Provider incidents and fail-closed design

Live public search was tested twice on 9 October 2026. DuckDuckGo returned
HTTP 202, Mojeek 403; Bing pages were rejected by the relevance filter.
Do not fabricate a LinkedIn result by widening the keyword query. The
collector now observes the existing reliable search circuit and returns
PROVIDER_DEGRADED/CIRCUIT_OPEN when appropriate. Freshness labels distinguish
cached historical results from new evidence.

## Operations, learning, and metrics

- Existing `empire-community-intent.timer` (15 minutes) is reused.
- Existing commercial relationship reconciliation incorporates sourced
  intent and proposed offer hypotheses into the private founder registry.
- Track community source, observation URL, timestamp, intent class,
  product hypothesis, identity corroboration, verified contact and any
  downstream conversation/payment separately.
- Avoid mistaking a Reddit score for revenue: no recipient, offer send, buying
  relationship, payout or realised revenue can be inferred from social content.
- Review source quality (accepted relevant observations / returned pages /
  attributable business identities / verified opportunities) before expanding
  collection volume. No third-party paid APIs or extra timers were installed.

**Remaining genuine blockers:** authenticated social-to-business attribution,
publisher/buyer commercial qualification and fresh LinkedIn public search
provider availability. All outbound remains founder-gated.


## Adaptive execution memory and autonomous next research task

The same existing 15-minute `scripts/run_community_intent_cycle.py`
implements `empire_os/community_intent_learning.py`. It writes an
idempotent, bounded operational learning journal at
`runtime/community_intent/source_learning_latest.json` (maximum 512
episodes). There is **no new timer, autonomous code rewrite or new CRM**.

Per successful or failed public Reddit research attempt, the journal
captures: source, collection slot, HTTP/collector outcome, number of truly
new posts, distinct explicit solution requests, self-reported operator
problems, seller pitches, and the next safe research action.

Automatic source selection follows three fail-closed rules:
1. Newly configured public communities are sampled before high-scoring
   historical communities are exploited.
2. Historical *research usefulness* and provider reliability adjust
   priority; a hard maximum-idle rule prevents source starvation.
3. Retries inside the same 15-minute slot do not create duplicate history,
   outcomes, conversion labels or billing events.

The existing buyer-commercial registry reads that operational journal and
displays the next research task alongside the Gmail/intent review. An
unavailable or malformed journal is explicitly marked unavailable, without
taking down the warm-buyer conversation workflow.

**Important:** observed Reddit/LinkedIn posts, internal research-task
completion and heuristic request classifications are *not* verified
commercial conversions. Cortex and Economic Memory require canonical
independently verified commercial outcomes (and payment/fulfilment for
a positive revenue label). The learning journal may reprioritise permitted
public research only. It cannot self-edit source code, activate outreach,
sign terms, change product prices or recognise revenue.

Proof standard: tests for idempotence, recency, fail-closed source health,
balanced exploration, operator-vs-seller relevance, no commercial claims,
cross-cycle persistence and shared-registry read-back.


## Bounded intent-to-company research tasks

`empire_os/intent_company_research_tasks.py` now converts only relevant,
time-bounded social observations into **identity research tasks within the
existing private commercial relationship registry**. The 30-minute buyer
scout invokes that registry reconciler; no duplicate CRM or research timer.

Research tasks contain: a stable hash of the source URL, source, observation
time, classified problem/request, candidate product hypothesis, evidence
links if present, outstanding company/author/budget/contact verification,
first-seen timestamp and last-evaluated timestamp. An unchanged source URL
preserves the task identity and original discovery timestamp across refreshes.

Posts that are hiring advertisements, career advice, seller outreach, product
self-promotion or general content **do not** enter the company-identity task
queue. High numeric scores are insufficient to overcome those exclusions.
Bound the queue to 12 research items, with balanced Reddit/LinkedIn coverage.

Even if a public social post quotes a known company website, the connection
remains an *unverified citation hypothesis*. No social identity, new
prospect, email address, commercial terms, approval or conversion can be
created from this evidence. Tasks always require independent company and
poster identity verification followed by ordinary consent, deliverability
and founder gates. No automatic direct messages or paid API access.

A research task is not marked complete by generation, and the commercial
outcome remains unknown until genuine counterparty and canonical revenue
evidence exists. Source-order learning remains in the existing
`source_learning_latest.json` journal; Cortex/Economic Memory own verified
commercial labels.


## Public first-party corroboration of social identity (9 October 2026)

The existing commercial-registry reconciler now optionally reads a private,
bounded manual public-evidence file:
`runtime/buyer_network_intelligence/intent_company_identity_evidence_latest.json`.
This evidence feed is **not** a new CRM, scanner, outbound gateway or timer.

Each record must link an exact shortlisted public post to a professional
public profile and an independent first-party business page that identifies
the same person. The official page URL must belong to the stated company
domain; mismatched domains, unsupported social sites, duplicate post IDs
and files without private permissions fail closed.

The two reviewed matches were:

- **Manning Pest Services** (manningpestservices.com): Chase Manning's public
  LinkedIn post seeks Tulsa-area local SEO for his own pest-control business;
  his company's About page lists him as founder. Independent public
  evidence: https://www.manningpestservices.com/about and
  https://www.linkedin.com/in/chase-manning-24712353 .
- **Shivya Ayurveda** (shivyahealthcare.com): Sahil Aggarwal's public post
  seeks technical SEO/GEO/AEO for a brand; Shivya's About page independently
  names him as founder. The site/profile association is supported, but the
  target brand for that particular request is not independently confirmed.
  Evidence: https://shivyahealthcare.com/pages/about-us and
  https://in.linkedin.com/in/sahil-aggarwal-2b1a99221 .

These dated public posts could represent requirements that have already
been fulfilled. The first-party links are a **reviewed company-affiliation
lead**, not proof of a current offer, identity of an email recipient,
commercial budget, buying authority, consent, founder approval, billable
calls or realised revenue.

Reviewed records can improve the order of identity-research tasks, but
`source_attribution_proven`, `verified_buyer_intent`,
`person_contact_verified` and `founder_outreach_authorized` remain false.
No new prospect is written by the review, and only the existing founder
commercial registry displays the evidence.
