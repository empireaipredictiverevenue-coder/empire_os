# Empire Search Product — Open Source Intake

Date: 2026-09-20
Purpose: reuse high-value open-source SEO/AEO/GEO capabilities without replacing Empire's canonical Search Intelligence evidence model.

## Rules
- Empire Search Intelligence remains the source of truth.
- Open-source components may supply collection, crawling, measurement, UI/workflow patterns or adapters.
- No component may invent keyword volume, ranking, authority, citations, traffic or revenue.
- MIT / Apache-2.0 components may be embedded or adapted with required notices preserved.
- Strong-copyleft components such as AGPL stay isolated behind a service/API boundary unless separately reviewed.
- Paid third-party data providers are optional adapters, never canonical truth or a hard dependency.
- External crawling/search must preserve provenance, robots/terms awareness and source-specific constraints.

## Tier A — strong candidates to adapt

### OpenSEO — MIT
Repo: every-app/open-seo
Use:
- MCP / agent-skill patterns;
- keyword research and rank-tracking workflows;
- local SEO / Maps-grid product patterns;
- GSC URL inspection / project context;
- domain/competitor/backlink workflow design;
- provider adapter architecture.
Do not hard-bind Empire to DataForSEO. Build provider-neutral adapters and use observed-source provenance.

### SEOnaut — MIT
Repo: StJudeWasHere/seonaut
Use:
- crawler audit issue taxonomy;
- severity model;
- broken-link / redirects / duplicate metadata / heading-order checks;
- technical-audit workflow patterns.
Best destination: Technical Search Audit product.

### SerpBear — MIT
Repo: towfiqi/serpbear
Use:
- keyword rank-history data model;
- scheduled rank checks;
- position-change alerts;
- Search Console integration patterns.
Best destination: Search Opportunity Map + Search Growth Command.

### Unlighthouse — MIT
Repo: harlan-zw/unlighthouse
Use:
- whole-site Lighthouse orchestration;
- smart sampling;
- performance/CWV reporting workflow.
Best destination: Technical Search Audit.

### Google Lighthouse — Apache-2.0
Repo: GoogleChrome/lighthouse
Use:
- performance/accessibility/best-practice measurements;
- Core Web Vitals and diagnostics.
Best destination: Technical Search Audit.
Prefer invoking maintained Lighthouse rather than forking its internals.

### SiteOne Crawler — MIT
Repo: janreges/siteone-crawler
Use:
- high-performance Rust crawl engine;
- SEO/security/performance crawl modes;
- markdown export for evidence extraction;
- optional self-hosted AI endpoint patterns.
Best destination: crawl/evidence acquisition adapter.
Integrate as a subprocess/service adapter before copying internals.

## Tier B — pattern donors / selective reuse

### All-In-One Free SEO Tool — MIT
Repo: IamRamgarhia/SEO-Tool
Use:
- multi-client/agency workflow patterns;
- lead-from-audit workflow;
- audit -> proposal/report flow;
- AI citation monitoring ideas;
- tech-stack-aware recommendation patterns;
- MCP product workflow ideas.
Do not import its SQLite source-of-truth model into Empire.
Verify individual data acquisition methods/terms before adopting.

### GPT Researcher — Apache-2.0
Repo: assafelovic/gpt-researcher
Use:
- cited research workflow for original market/content research;
- source-backed report generation.
Best destination: Search Opportunity research briefs / citation-worthy original research.
Not a ranking measurement source.

## Reference-only / not adopted

### Firecrawl — AGPL-3.0 core
Repo: firecrawl/firecrawl
Status: REJECT_FROM_RUNTIME / REFERENCE_ONLY.
Empire already owns its crawler/search evidence stack and does not need Firecrawl as a runtime dependency or service dependency.
We may compare public product behaviour and ideas, but do not import, embed, fork or operationally depend on the AGPL core.

## Empire Web Intelligence Crawler — CANONICAL
Empire's crawler stack is the canonical collection/evidence layer:
- site_crawler.py for bounded first-party contact crawling;
- Search Fabric site_probe for HTML/schema/people/contact/service-area evidence;
- sitemap/common-path discovery and bounded page walking;
- first-party person/title recovery;
- structured-data extraction;
- email/phone quality guards;
- canonical URL cleanup and evidence provenance;
- multi-engine Search Fabric fusion;
- direct-business/directory/article classification;
- geo/entity/consensus/confidence scoring;
- acquisition routing into canonical Supabase and Intelligence Fabric.

Search Product work should enhance this stack rather than introduce a second crawler source of truth.

## Empire-native capabilities we keep
- canonical tenant-scoped Search repository;
- evidence provenance;
- indexation lifecycle;
- content decay;
- cannibalisation;
- internal links;
- backlink evidence;
- AEO/GEO citation observations;
- citation gap;
- competitor gap;
- sitemap/robots governance;
- Search -> recognized revenue attribution;
- OBSERVE/recommendation authority gates;
- Founder/Search Command Centre integration.

## First product set
1. Technical Search Audit.
2. Search Opportunity Map.
3. Content Decay & Cannibalisation Monitor.
4. Authority & Backlink Intelligence.
5. AEO / GEO AI Visibility.
6. Competitor Search Gap.
7. Search Growth Command.

## Next implementation slices
1. Add crawler adapter contract.
2. Add Lighthouse/Unlighthouse adapter.
3. Add rank-history contract inspired by SerpBear/OpenSEO.
4. Add local SEO / Maps-grid product contract.
5. Add technical issue taxonomy/severity model from SEOnaut patterns.
6. Add audit -> client brief/report contract.
7. Add provider-neutral keyword data adapter; DataForSEO remains optional.
8. Add provenance-aware AI citation observation collector.
9. Add first-party analytics adapter for Search -> lead -> revenue attribution.
10. Surface all products and readiness in Search Command Centre.


## 12 November 2026: original Jev + Browser Operator in unified Search Engine

**This is an extension of the existing Search Intelligence/Founder Console and its original Browser Operator owner; do not create an independent browser service, SEO department, dashboard, database or authority plane.** Founder direction: all reviewed open-source SEO/AI capabilities, SEO microsites, Jev and the original Browser Operator belong to **one engine and one Founder website**. Existing source owners and approval gates remain authoritative.

### Recovered runtime contracts (read-only verified 12 November)

| Original component | Reused contract | Evidence/state | Integration role |
| --- | --- | --- | --- |
| SEO Director / Search Intelligence | `empire_os/search_intelligence/seo_director_review.py` and `/v1/search/jev/department/review` | Loopback 8771 GET 200, Jev department `task_count=14`, `jev_inference_calls=0`, `mode=OBSERVE`, `execution_authority=NONE` | One source-grounded action selector and SEO department owner; Jev triage does not independently authorise actions |
| Jev deployment evidence | `/v1/search/jev/deployment/summary` | Loopback 8771 GET 200, `mode=RESEARCH_TO_RELEASE_READY`, `execution_authority=NONE` | Original research-to-release review; never treat a model prediction as a published/indexed result |
| Original Browser Operator | `/home/ubuntu/empire_worktrees/empire_browser_operator_20261021/tools/browser_operator/` (`task_brain.cjs`, `jev_action_selector.cjs`, `browser_session_broker.cjs`, `task_authority_bridge.cjs`, `task_ledger.cjs`, `operator.cjs`) | Source branch `0278f30ce` inspected; private Founder release `browser-task-observe-20261105v2` already activated and verified | Permissioned page/SERP/competitor/microsite inspection, screenshots, safe same-origin navigation, task-specific observable verification and held-action receipts; no new service |
| Browser evidence API | `/v1/founder-execution-plane/browser-tasks/recent` on existing private loopback 8766, private `/founder/browser-tasks` on 3001 | GET 200, `READONLY_EVIDENCE_FEED`, `read_only=true`, `execution_authority=none`; unauthorized write requests denied, public route not enabled | Source-backed per-task evidence into existing authenticated Founder Console; never expose raw browser text, credentials, cookie/session data, screenshots or full task context in public aggregates |
| Existing original microsite and helpful-content portfolio | `/tools/revenue-leak-check`, `/roofing/replacement-vs-repair`, `/roofing/installation-checklist`, `/aeo/roofing/DFW` | All four HTTPS 200 with canonical and `index,follow` in observed source/header on 12 Nov; this does NOT prove Google indexing or organic traffic | Same crawl/indexation, keyword intent, browser QA, analytics and real consented CRM/revenue funnel as core site; preserve separately approved editorial and consumer-contact gates |
| Open-source SEO/AI research | Existing approved intake above plus `docs/seo/OPENSEO_FREE_DATA_AND_EMPIRE_BRIDGE_20261016.md` in original isolated worktree | OpenSEO snapshot pinned, original GSC Keyword Universe bridge previously built; 16/16 isolated unit tests pass on 12 Nov; not production-integrated | OpenSEO, SEOnaut, SerpBear, Unlighthouse, Lighthouse, SiteOne, GPT Researcher, Claude SEO, SEO Machine, Crawl4AI and AI-citation evidence candidates supply bounded adapters/skill patterns, subject to exact project/version/licence/security and provider assessment; not independent agents/databases |

### Single end-to-end contract

1. **Evidence intake:** first-party GSC (property totals separated from sampled query/page evidence), optional GA4/consented first-party analytics, permitted Search Fabric/competitor/market providers, page crawls and canonical Smart CRM outcome receipts. Every series carries source, dimension, date window, observed/estimated type, cost, freshness and evidence fingerprint.
2. **Decisions:** SEO Director turns genuinely new search/buyer intent evidence into an original owner work item. Existing Jev can choose/score/hold *only* typed, validated alternatives and approved observation/research lanes. It cannot confer task authority; unverified rank/traffic/price/backlink/revenue remain unknown.
3. **Browser hands:** original Task Brain routes bounded read-only browser checks (real SERP/page content, technical defects, competitor examples, microsite journeys, mobile/desktop screenshots and pre/post-release verification) through canonical capability/policy rules. Jev is an optional browser action selector, not a replacement browser agent. No login bypass, non-GET external writes, form sends, publishing, purchases, outreach or paid inference without the separate existing gates. DOM and third-party content remain untrusted.
4. **Website/microsite release:** exact original website/ASTRA/DesignOS owner integrates and verifies approved changes; browser GET-only smoke, mobile visual QA and form POST interception may verify candidates. Founder-approved protected publication/rollback authority remains separate. An SEO review or green browser test is not a live publication.
5. **Measure:** page/keyword/country/device trends, technical status, actual AI citations, and deduplicated consented CRM funnel to accepted deals/recognized revenue. The Founder Growth interface must mark unknown as unknown and distinguish model decisions, completed research, executed browser checks, implemented source, live released content, Google observations and real commercial outcome.
6. **One authenticated website:** the original Next.js Founder Console should present Search, Competitors, Technical, AI Visibility, Microsites, Browser Evidence, SEO Work and Revenue drilldowns from these **existing** reader services; all date/source/market/industry filters reconcile to a single provenance contract. The 33012 dev page and actual 3001 private release are not interchangeable: verify actual served source before merging or releasing.

### Confirmed 12 November integration defect

The original Browser Operator's live Founder feed is **a bounded recent list**, not a historic analytics source. The ledger directory contains **357 `task-*.json` files** on the observed run; the private API returns only the latest 50 when `limit=50`. The earlier BOXT and Aura research receipts were found at recency positions 58 and 57. A pinned historical regression (`tests/test_browser_task_founder_release_candidate_20261105.py`) incorrectly expects those receipts within the latest 50: the focused test run yielded **65 pass, 1 fail**. The source records were observed on disk, so this failure is an age/window assumption, not proof of their deletion. The **original Browser Operator owner** should update the stale test and design a bounded historical aggregate/pagination contract that remains private, source-verified and never silently truncates a plotted history. Do not change the live private overlay without its owner's controlled release.

**Next original-owner integration:** Browser Operator owner supplies safe evidence/time-series reader; original SEO owner consumes it in the existing Search Intelligence decision/measurement contract; current Founder Console owner reconciles the actual running private pages with SEO Operations and microsite analytics; ASTRA retains guarded publication. Do not duplicate worktrees, workers, queues, dashboards, databases, paid provider calls, customer submissions or public routes.
