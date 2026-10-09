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
