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
