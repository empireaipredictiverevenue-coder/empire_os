# GROWTH-001 — UK AI readiness buyer-intent and competitor research

**Research date:** 16 October 2026. **Existing department:** Empire AI `marketing_growth`. **State:** OBSERVE/EDITORIAL REVIEW; not a campaign release or an actual Google ranking report. **Budget:** £0. **Website:** ASTRA's unfinished website is not to be edited.

## The verified commercial question

Prospective UK buyers need to decide whether to pay for an AI assessment, what it would actually cover, what assumptions go into a return-on-investment scenario, and what happens when evidence suggests AI is not the answer. Broad "AI readiness" text alone won't answer this.

**Search hypotheses requiring real demand validation:** `ai readiness assessment uk`; `ai readiness assessment cost uk`; `ai audit deliverables`; `ai opportunity assessment cost`; `ai implementation roi assessment`; `what to ask an ai consultant before paying`. These are *hypotheses*, not verified search volumes, keyword difficulties, top-ten ranking positions, or buyer enquiries.

## Public competitor pages checked (16 October, advertised terms only)

| Publisher | Public reference | Advertised amount | Public buyer proposition | Empire content gap to address |
|---|---|---|---|---|
| Indexify | https://indexify.co.uk/pricing | One-team audit **from £3,000 + VAT** | Identified outputs and defined initial pilot, about two weeks | Buyer needs scope and deliverable comparisons, not our unverified equivalence |
| CodeLeap | https://codeleap.co.uk/services/ai-readiness-assessment/ | **£3,000** | One-week assessment, illustrative ROI and scope steps | Explain uncertainty, evidence needed and exclusions with no implied delivery timeline |
| AferStudio | https://aferstudio.com/ai-audit | **£5,000–£10,000** | Process map, data readiness, prioritisation, roadmap, fixed-fee engagement | A useful checklist that separates *requested* output from *contracted* output |
| Augustova | https://www.augustova.co.uk/guides/how-much-does-an-ai-consultant-cost-uk | Their own audit **£2,500–£6,000** | Date-stamped 12-provider price table and audit-vs-build comparison | Our £2,500 entry is not unique or guaranteed better: focus on verifiable decision evidence |
| Sharp Code | https://www.sharpcode.co.uk/insights/ai-readiness-assessment-cost-uk-2026 | Market discussion: free self-checks, paid options varying by scope | Buyer FAQs and service/range comparisons | Don't imply every assessment is equivalent or borrow unsourced ranges |

**Caveats:** Advertised competitor amounts are not invoices or proof of fulfillment. These are publisher-owned pages located through public web research, **not** a verified Google Top 10, ranking position report, advertising-spend dataset, organic-traffic estimate, competitive backlink inventory or a quote from any of these suppliers to Empire AI. Their offers have materially different promised deliverables; comparing their price to Empire's unscoped starting price is not like-for-like.

## Primary official buyer evidence worth referencing accurately

- The UK [DSIT AI Adoption Research](https://www.gov.uk/government/publications/ai-adoption-research/ai-adoption-research), updated 13 February 2026, conducted **3,500 UK business interviews** February–May 2025. It reported **16%** currently using at least one AI technology in *its* covered population, and **77% of users reporting no revenue change** at that time. Survey estimates and definitions matter. This does NOT mean 77% of implementations fail or prove anybody should buy consultancy. It suggests buyers ought to distinguish productivity stories from actual revenue evidence.
- The [ONS Business Insights bulletin, 8 October 2026](https://www.ons.gov.uk/businessindustryandtrade/business/businessservices/bulletins/businessinsightsandimpactontheukeconomy/8october2026), reported **30%** of businesses in September 2026 using at least one AI technology, with a different population, method and period. **Do not present DSIT 16% → ONS 30% as a directly comparable growth series** or infer Empire's customer readiness. ONS classifies these as official statistics in development and advises caution.
- Google's [title-link advice](https://developers.google.com/search/docs/appearance/title-link) and [non-commodity content guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) favour unique descriptive titles and substantive reader value, not keyword repetitions in every heading or hundreds of similar generated URLs.

## Positioning: say what Empire actually offers

The first-party `/v1/checkout/commercial/offers` catalogue reports, as of this observation:

- **Opportunity Assessment, from £2,500 excluding applicable VAT**, one-time.
- **Strategy Blueprint, from £7,500 excluding applicable VAT**, one-time.
- **Strategic Advisory, from £3,000/month excluding applicable VAT**.

All three are `FOUNDER_LED_PROPOSAL_ONLY` with `delivery_scope_verified=false`, `binding_terms_ready=false` and `checkout_enabled=false`. Do not promise a one-week deliverable, a specific ROI, a full audit report, a fixed costed roadmap, available delivery capacity, immediate checkout or a signed contract; scope and terms need an individually approved proposal.

**Our differentiator for the reader:** traceable research sources, risk and assumption checks, a worked hypothetical ROI worksheet with zero false customer stories, and a **nonbinding path to scope an engagement**. We can demonstrate the methods we use to evaluate evidence before discussing implementation. This is a *writing strategy*, not proof Empire is currently more effective than any supplier.

## What the SEO and editorial desks should do next

1. **Demand desk:** document timestamp, UK locale, search phrase, actual organic results, observed publisher intent, and first-party GSC query/page performance; mark estimated volume and rankings `UNKNOWN` until measured. A web-search discovery list does **not** establish Google rank.
2. **Editor:** update the exact first-party offer description and price, compare buyer questions (scope, cost, data, ROI, responsible reviewer, failure exit) and preserve real official citations. Don't copy competitor copy.
3. **Commercial owner:** define written scope, output acceptance criteria and who can fulfill an assessment before the public page says what is included.
4. **Technical SEO:** first confirm `/commercial` indexability and eventual actual GSC indexed state, using the existing Search Intelligence observer. No mass indexing submissions.
5. **ASTRA owner:** site still unfinished; do not change source or publish an SEO page just because a draft exists.
6. **Founder:** exact asset and scope approval once all preceding evidence gates are met. No paid traffic, autoresponder, outreach or payment activation in research.

**Campaign outcome today:** competitor comparison and primary-source factual verification completed; campaign search volume, current Google rank, conversion and realised revenue UNKNOWN. This is a stronger editorial research packet, not proof of a business result.

## First-party SERP-source validation: negative result, retain UNKNOWN

The already-running EmpireOS Search Intelligence `POST http://127.0.0.1:8771/v1/search/serp/snapshot` endpoint was invoked **three times only**, explicitly using its existing no-key, no-fee `bing_html` engine with eight requested organic results. The attempted topics were `ai readiness assessment UK cost`, `AI opportunity assessment UK consultancy` and `AI readiness audit UK deliverables`. The service returned HTTP 200 with each snapshot `engine=none`, `available=false`, `quality_gate=null`, `error=All engines failed` around **12:38 UTC 16 October 2026**. Therefore **zero trustworthy engine positions** and **no independent search-volume measurements** were captured. The service was not restarted and no Search Fabric source/credentials were modified.

This is an upstream search-provider evidence limitation, not proof the phrases have no demand. The competitor research above originated from openly readable publisher webpages, and remains useful for editorial planning but **cannot** be represented as exact live Google or Bing ranks. The existing Demand Intelligence owner should repair/test its current bounded source or collect authorised owner-visible Search Console/Trends observations; do **not** build a second SERP scraper or acquire another server. Do not publish or approve a "low-competition 24-hour ranking" campaign from these results.
