# Empire AI SEO/AEO/GEO Editorial Quality Standard + Campaign GROWTH-001

**October 16, 2026 · OWNER-REVIEW DRAFT · NOT PUBLISHED.** This is a human-readable editorial acceptance contract for the **existing** Marketing & Growth department. It creates no SEO agent, no crawler, no Slack workspace, no persistent workflow, no CMS publisher, no automated email, no database or billable service. The ASTRA flagship website is under active development and is **not** part of this task.

## Why the rules are structured this way

Google Search Central recommends page-specific, concise `<title>` elements and a clear primary heading describing the page, readable and distinct subsection headings, and good source-based content. **There is no Google requirement to copy the exact keyword into every H2 or H3.** Repeating the same phrase throughout the headings can be keyword stuffing. Google also does not impose a hard meta-description character limit or guarantee it will display the supplied text; any length bands below are internal editor convenience, not Google ranking factors.

Primary, current references: [Google title links](https://developers.google.com/search/docs/appearance/title-link), [SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide), [meta description guidance](https://developers.google.com/search/docs/appearance/snippet), [links and descriptive anchor text](https://developers.google.com/search/docs/crawling-indexing/links-crawlable), [2026 generative AI advice](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide). Important Google AI Search point: an indexable page must contain genuinely useful content; no `llms.txt`, artificially chunked text or made-up FAQ schema is necessary or guaranteed to earn an AI citation.

### Department editorial desk quality checklist

1. **Campaign and user intent:** identify real buyer problem, primary query **hypothesis** and region, secondary user questions, published URL status and source confidence. Demand volume stays `UNKNOWN` until observed in authorized Search Console, reliable keyword research or source-specific SERPs; do not infer it from unrelated web search results.
2. **Title:** one unique, meaningful, concise document `<title>` naturally expressing the primary search topic and brand. Do not string synonyms or copy the phrase repeatedly. This is not a fixed Google character limit.
3. **H1:** a single visually dominant, accurate page heading (the target idea appears naturally; it need not be a verbatim copy of the SEO title). Match the actual page content. Avoid multiple competing visual headlines.
4. **H2/H3:** structure the reader's decision, not the keyword count. Distinct H2 questions tackle cost, scope, risk, process and outcome; H3 answers narrower real follow-up questions under an H2. No skipped hierarchy, repetitive subheadings or thin unanswered question sections. Relevant variants are better than repeated phrases.
5. **Main answer and originality:** answer the leading question in ordinary language in the opening, then use genuinely original decision matrices, verifiable examples, assumptions and practical worksheets that outperform existing pages. Don't reproduce competitors' wording or invent case studies, expert identities, customer numbers or results.
6. **Source provenance:** support claims with public primary source citations, correct methods/populations/dates and rights, clearly distinguish third-party studies from Empire customer results, and flag internal expert review. Recheck time-sensitive numbers at sign-off.
7. **UX and accessibility:** meaningful HTML text, ordinary crawlable internal `<a href>` links with readable anchor text, accessible tables/images where needed. Link only to existing, relevant, indexable/compliant pages and a consent-respecting enquiry route; provide understandable CTAs without fake scarcity.
8. **SEO/AEO/GEO:** distinct title/meta description, intended canonical and site owner, purposeful user questions with direct answers, correct visible source links, optional accurate structured data only where eligible. No guarantee of AI Overview inclusion or GEO citations.
9. **Commercial truth:** verified public offer names and prices, VAT disclosure, delivery/contract uncertainty and nonbinding scope where appropriate. A draft's click, lead, accepted payable event and realised revenue remain separate unknowns until first-party proof.
10. **Release governance:** SEO editor, source fact checker, commercial/legal/brand QA, existing site owner ASTRA and founder approval all retained. Passing static quality checks means **ready for human review**, never publication authority.

## First campaign: UK AI Readiness Assessment

**Campaign register:** `GROWTH-001` in `ORGANIC_GROWTH_DEPARTMENT_RESEARCH_PORTFOLIO_20261016.json`. The full structured brief is `GROWTH_001_AI_READINESS_ARTICLE_BRIEF_20261016.json`; draft article is `GROWTH_001_AI_READINESS_ARTICLE_DRAFT_20261016.md` (around 1,100 public-copy words excluding internal editor notes).

| Field | Proposed reviewer-verified value |
|---|---|
| Primary keyword hypothesis | `AI readiness assessment UK` |
| SEO `<title>` | `AI Readiness Assessment UK: Cost, Scope and ROI | Empire AI` |
| H1 | `AI Readiness Assessment for UK Businesses: Cost, Scope and ROI` |
| H2 reader questions | What an assessment is; what it costs; which data/processes; ROI and risk; next step |
| Original element | A 200-task hypothetical monthly ROI scenario and five-row evidence/stop-rule checklist; illustrative values are NOT customer evidence |
| Primary source 1 | [DSIT 2026 AI Adoption Research (survey from 2025)](https://www.gov.uk/government/publications/ai-adoption-research/ai-adoption-research) |
| Primary source 2 | [ONS 8 Oct 2026 Business Insights](https://www.ons.gov.uk/businessindustryandtrade/business/businessservices/bulletins/businessinsightsandimpactontheukeconomy/8october2026) |
| Product/CTA | Founder-approved starting price **£2,500 excluding applicable VAT**, and [nonbinding enquiry](/commercial); delivery scope and binding contract NOT verified |
| Internal pathways | `/commercial` and `/trust`, both already live, with human-readable contextual anchor text |
| Ranking / search volume | UNKNOWN, not validated by article quality testing |
| Indexation | `/commercial` was recorded **unknown to Google** in last available URL Inspection, 16 October; normal crawl lag applies |
| Deployment status | DRAFT_ONLY, **not live**, no ASTRA code changes |

The separate [Augustova AI audit research](https://www.augustova.co.uk/guides/ai-readiness-audit-uk-sme) and [Sharp Code price breakdown](https://www.sharpcode.co.uk/insights/ai-readiness-assessment-cost-uk-2026) demonstrate that baseline price and checklist articles are already common. Our differentiated approach should be **transparent assumption models, stop rules, exact primary statistical sources, and precise nonbinding commercial evidence**, rather than another generic AI-generated article. These are competitive examples, not authoritative evidence of keyword position or volume.

### Quality gate and result

```bash
cd /home/ubuntu/empire_worktrees/search_growth_department_research_20261016
/srv/empire_os/.venv/bin/python scripts/review_search_editorial_quality_20261016.py --review-only
/srv/empire_os/.venv/bin/python -m pytest -q \
  tests/marketing/test_search_editorial_quality_20261016.py \
  tests/marketing/test_search_growth_department_portfolio_20261016.py \
  tests/test_marketing_agency.py
```

Observed result: `EDITORIAL_STRUCTURE_PASS_HUMAN_REVIEW_REQUIRED`, SEO title/H1 aligned, **six H2**, three H3, seven useful question headings, two independently sourced first-party external official links, 2 existing internal links, no verbatim keyword repeated in H2/H3, correct £2,500 *nonbinding* starting-price disclosure. All falsehoods/keyword stuffing tests reject as designed. The complete combined run returned **64 passing tests** as of 16 October 2026. These are deterministic *editorial* checks, not independent content expert approval or Google quality/ranking certifications.

### What is still held

- No verified search demand/keyword competition rank for `AI readiness assessment UK` yet; competitor pages observed in exploratory web research are **not** position-verified Google SERP snapshots.
- The £2,500 public catalogue's `delivery_scope_verified=false`, `binding_terms_ready=false`, `checkout_enabled=false` are preserved. A founder-approved written engagement scope would be needed before claiming deliverables.
- The website belongs to ASTRA and the flagship redesign is **unfinished**. Do not publish this draft, create a new page, replace `/commercial`, or change sitemap/canonicals from this branch.
- No live enquiries, paid conversions, generative citations, backlinks or downstream revenues are attributed to this **unpublished** draft.
- Editorial source/claim review, privacy/brand/accessibility approval, specific user-intent SERP sampling and conversion review remain with existing functional owners.

## Slack decision

**Slack is not required.** Existing `marketing_growth` Marketing Director, Search Intelligence/SEO Director, ASTRA coordination, founder dashboard and governed approvals already provide the roles and communication system. An outside chat service cannot fix indexing or prove buyer demand. Do not make the user sign up or provision Slack as a campaign prerequisite. An authenticated optional integration may be considered later for a genuine human team, with the user's explicit action.

## Owner handoff

**Marketing Director / SEO research desk:** validate exact target query/locale and SERP/competitors in first-party search fabric; fail if intent/cannibalisation mismatch. **Editorial lead:** fact-check official source stats and assess whether the ROI example creates differentiated reader value. **Commercial owner:** verify proposed offer scope and founder contact reply flow without guessing fulfilment. **ASTRA:** no changes until independently owned website work and approvals permit a bounded change. **Founder:** review only the final exact article and release plan once the preceding evidence gates are closed.

**Success is not publication volume**: GSC indexed pages and qualified clicks → real consented enquiry → verified offer/accepted event → settled fulfillment → realized contribution. Each is a distinct verified stage, not a guessed chain.

## Founder clarification: no generic AI slop — describe the real business

**16 October 2026, founder direction:** Public Empire writing must lead with genuine customer problems and exactly what the business offers, not machine-generated sounding slogans or topical filler to exploit Google keywords. Keywords in the `<title>`, H1 and useful H2/H3 sections are to help a reader understand the page; a keyword phrase does not prove relevance, service readiness, ranking or revenue.

The live first-party founder-led commercial offer catalogue was rechecked on 16 October 2026 and shows **Opportunity Assessment from £2,500**, **Strategy Blueprint from £7,500**, and **Strategic Advisory from £3,000/month**, all with VAT applied where appropriate. For each consultancy item: `sale_mode=FOUNDER_LED_PROPOSAL_ONLY`, `delivery_scope_verified=false`, `binding_terms_ready=false`, `checkout_enabled=false`. Therefore the article now has a dedicated section, **“Which Empire AI service can help with an AI readiness decision?”**, that explains the service option, starting price and actual proposed enquiry route, with explicit caveats about unconfirmed deliverables, availability and contractual terms. It links to the real `/commercial` page rather than pretending to have a new paid product checkout.

A separate concise, nonpromissory company description for marketing and editorial is now available at `docs/marketing/VERIFIED_EMPIRE_SERVICE_DESCRIPTION_20261016.md`. It distinguishes the three consultancy starting-price policies from independent listed commercial-intelligence products and from the broader Predictive Revenue platform still under development. It does not claim customer case studies, immediate availability, delivered services, revenue growth or payments.

The editorial reviewer now validates **three exact named consultancy options and approved price/billing terms**, requires a specific nonbinding service explanation and rejects unsupported claims of delivered customer results, false price or catalogue status, and common hype templates such as “unlock the power of AI,” “game-changing AI solutions,” “revolutionize your business” and “cutting-edge solutions.” This is a deliberately conservative internal heuristic, **not Google's proprietary SEO algorithm**, and a human is still responsible for assessing whether a statement is true and useful. The expanded combined test suite now passes **73 tests** (including existing marketing agency tests).

**Release state unchanged:** not live, no website source edited, no outbound, no payments, no changes to ASTRA's unfinished flagship build, no new SEO infrastructure. Verify final facts against the *current* first-party offer API before any owner-approved publication, since proposals and delivery readiness can evolve.

## October 16, 12:35 UTC — real UK buyer competition review and primary-source correction

**Public competitor research** is captured in `GROWTH_001_UK_COMPETITIVE_SEARCH_BUYER_INTENT_RESEARCH_20261016.md`. It compares official published offers by Indexify (from £3,000 + VAT), CodeLeap (£3,000), AferStudio (£5,000–£10,000), and Augustova (their own stated £2,500–£6,000) with pricing/service disclosure caveats. **This is public-web source discovery; NOT verified live Google rank positions, organic keyword volume, purchases, fulfilment or backlinks.** The conclusion is that publishing a generic list of AI audit prices would enter an already crowded information format; the differentiator needs to be a verifiable, reader-useful business decision framework and a truthful description of Empire's three founder-reviewed consultancy options.

The edited `GROWTH_001_AI_READINESS_ARTICLE_DRAFT_20261016.md` now specifies the distinct DSIT and ONS methodology/time windows: DSIT's 3,500-business February–May 2025 interview set reported 16% use of an AI technology and 77% of AI users reporting no change to revenue *at that point*. ONS's September 2026 AI indicator in its 8 October bulletin reports 30% use within **its different survey design**. These figures are **not** a direct change series and do **not** claim that customer AI projects are useless or that Empire did better. The article adds a section on how to compare written consultancy quotations fairly, explicitly distinguishing the likely questions a buyer should ask from deliverables Empire has not yet contractually promised. The existing hypothetical ROI worksheet remains labelled purely illustrative, not a client case study or realised saving.

The reviewed draft's wording is now **approximately 1,420 public words** with **one SEO H1, seven H2 sections, four H3 subsections**, two dated official primary UK sources, readable contextual internal links and an opt-in, nonbinding first-party commercial contact. Main keyword use is natural: no forced exact phrase in every heading. Existing 73 combined tests pass and the company-specific service quality gate remains `EDITORIAL_STRUCTURE_PASS_HUMAN_REVIEW_REQUIRED`.

**Necessary before release:** actual UK-locale first-party/Search Console query demand or reliable SERP snapshot with rank provenance, reviewed final offer/fulfilment scope, human expert verification of exact primary-statistical wording, ASTRA website owner reconciliation, and specific founder approval. The commercial URL's indexed status and resulting referral revenue are still not proven. No deployment, website edit, indexing request, paid traffic, customer outreach or cash movement occurred.

### First-party search-fabric availability verification (16 October, 12:38 UTC)

Three attempted exact UK keyword SERP snapshots using the current, no-fee existing Search Intelligence `bing_html` provider returned `available=false, engine=none, error=All engines failed`. There were **no observed search positions**. Keyword difficulty and demand volume remain `UNKNOWN`, even though competitors' published pages were independently discovered. The campaign **cannot be called SERP-validated or ready to rank within 24 hours**. Existing Search Fabric owner should diagnose its own source/readiness before keyword launch approval. No new external SEO subscription, scrapers, agent, database or service was created. The full attempt and source-boundary notes are in `GROWTH_001_UK_COMPETITIVE_SEARCH_BUYER_INTENT_RESEARCH_20261016.md`.

### Separate earned-distribution desk research (16 October, 12:42 UTC)

`GROWTH_001_EARNED_DISTRIBUTION_RESEARCH_20261016.md` contains three independently discovered editorial sources: Compare the Cloud's UK technology practitioner-opinion guide, Business Info's explicitly published business-tech editorial submission route, and techUK's 2026 AI Innovation Focus Week. **TechUK's 12 October submission deadline is past**; it also rejects apparently AI-written and duplicate guest articles, so this opportunity is CLOSED, not a 'quick backlink' target. The other two are only *potential* routes, not guaranteed free, open, accepted or search-ranking beneficial. Any genuine expert contribution must be based on the founder's own demonstrable technical work and must comply with publisher rules and separate founder approval before contact. No editor was contacted, no article posted and no backlink or referral session recorded.
