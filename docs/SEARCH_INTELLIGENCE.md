# Empire Search Intelligence Engine

Status: foundation implementation, OBSERVE-only
Canonical database: Supabase project `owbeinlfcfdtwcwrttjy`
Canonical payment rail: USDT on BSC

## Purpose

Empire Search Intelligence is the governed SEO + AEO + GEO + commercial attribution layer for EmpireOS.

The target loop is:

```
SEARCH
→ INTENT
→ PAGE
→ VISITOR
→ PROSPECT
→ AI CONVERSATION
→ OPPORTUNITY
→ FULFILMENT / SALE
→ VERIFIED REVENUE
→ OUTCOME LEARNING
```

The system optimizes toward useful search assets and observed commercial outcomes rather than rankings or traffic alone. It must never manufacture keyword volume, competition, Search Console data, SERP snapshots, conversions, revenue, reviews, ratings, people, testimonials, or other business evidence.

## Architecture

`empire_os/search_fabric/` remains the canonical web-search/discovery substrate. It is not replaced.

`empire_os/search_intelligence/` sits above Search Fabric and owns search governance and interpretation:

- `models.py` — canonical page, opportunity, quality, metadata, schema, canonical and indexability records.
- `config.py` — hard-clamped OBSERVE authority for the foundation.
- `scoring.py` — deterministic opportunity scoring using observed inputs only.
- `quality.py` — mandatory content quality firewall.
- `metadata.py` — recommendation-only metadata projection.
- `schema.py` — visible-content-only JSON-LD preview generation.
- `canonical.py` — canonical URL issue detection and recommendations.
- `indexation.py` — explicit page lifecycle and auditable transition recommendations.
- `health.py` — module/integration readiness status.
- `commander.py` — `SearchCommanderAgent`, currently recommendation-only.
- `api.py` — FastAPI routes under `/v1/search`.

Legacy AEO/SEO scripts remain compatibility code. Direct page publishing/removal, old `/root` feedback paths, and legacy bulk generation are not the authority for new Search Intelligence behavior and must not be expanded around the new governance layer.

## Execution Policy

Current mode is always `OBSERVE`.

Allowed:
- inspect health and stored state;
- calculate quality and opportunity scores from supplied observed inputs;
- recommend metadata, schema, canonicals, indexability and lifecycle transitions;
- report missing integrations/evidence explicitly.

Blocked in OBSERVE:
- publishing or deleting pages;
- redirects;
- changing production content;
- changing robots or canonical tags;
- submitting sitemap/indexing requests;
- mass-generating pages;
- changing search campaigns;
- autonomous Search Console or SERP writes presented as observed evidence.

Future `RECOMMEND` and `APPROVE_AND_EXECUTE` modes require separately reviewed authority and explicit production gates.

## Content Quality Firewall

Every programmatic or generated page must pass `ContentQualityEvaluator` before it can even be recommended for approval.

Inputs include:
- originality;
- useful content;
- intent coverage;
- factual support;
- source quality;
- topic completeness;
- page uniqueness;
- internal-link support;
- structured-data validity;
- user value;
- duplication risk;
- thin-content risk;
- unsupported-claim risk;
- keyword-stuffing risk;
- template-duplication risk;
- hallucination risk.

Unknown factors remain unknown.

Default behavior:
- insufficient/unsafe quality → `noindex,follow`;
- passing quality → `eligible_for_approval`;
- never auto-index from the quality evaluator.

## Opportunity Scoring

The initial deterministic model uses observed 0..1 inputs:

```
intent
× commercial_intent
× conversion_probability
× relevance
× authority_fit
× freshness
÷ competition
```

If a required factor is unknown, `opportunity_score` remains null and the result identifies the missing metrics. Keyword volume, competition and business value are never guessed.

## Indexation Lifecycle

Supported states:

`DISCOVERED → DRAFT → QUALITY_REVIEW → APPROVED → PUBLISHED → INDEXABLE → SUBMITTED → DISCOVERED_BY_GOOGLE → CRAWLED → INDEXED`

with governed branches for `DECLINED`, `NOINDEX`, `REFRESH_REQUIRED`, and `ARCHIVED`.

Transitions are explicit. In OBSERVE, a valid transition is only a recommendation and `execution_allowed=false`.

## Canonical Data Model

Foundation migration:

`supabase/migrations/20260918134000_search_intelligence_foundation.sql`

Initial tables:
- `seo_sites`
- `seo_pages`
- `seo_queries`
- `seo_opportunities`
- `seo_content_scores`
- `seo_indexation`
- `seo_search_console`
- `seo_revenue_attribution`
- `seo_alerts`
- `seo_refresh_queue`

All remain in the canonical Supabase/Postgres database. No second database is introduced.

RLS is enabled on the new tables. Public/anonymous/authenticated access is revoked. History/evidence tables are insert/select-only for the service role in the foundation migration; stateful search tables have the bounded CRUD surface needed for a future repository layer.

The migration is staged only. It has not been applied to production.

## Revenue Attribution

Search attribution joins to existing canonical commercial identifiers rather than creating shadow CRM identity:

- `prospect_id → prospects.id`
- `opportunity_id → gtm_opportunities.id`
- `fulfilment_order_id → fulfilment_orders.id`
- `commercial_event_id → commercial_events.id`

There is no canonical web-session/conversation table yet. Until one exists, session/conversation references remain explicitly external nullable IDs rather than pretending to be canonical relationships.

Only observed revenue tied to governed commercial evidence may populate revenue attribution. Forecasts, quoted amounts and modeled value do not count as actual revenue.

Target reporting:
- revenue per organic landing page;
- revenue per observed query;
- revenue per topic/industry/location;
- organic lead value and conversion rate;
- search-assisted revenue.

## Search Console and SERP

Google Search Console is not activated in the foundation. The schema is prepared for observed query/page/date/device/country/impression/click/CTR/position data.

If credentials are absent, the connector must report disabled/unavailable. Synthetic substitutes are prohibited.

SERP collection should reuse Search Fabric and future validated adapters. A SERP snapshot must contain real retrieval evidence and timestamp/provenance; fake snapshots are prohibited.

## API

Foundation routes:

- `GET /v1/search/health`
- `GET /v1/search/summary`
- `GET /v1/search/pages`
- `GET /v1/search/opportunities`
- `GET /v1/search/indexation`
- `GET /v1/search/decay`
- `GET /v1/search/cannibalisation`
- `GET /v1/search/alerts`
- `GET /v1/search/revenue`
- `POST /v1/search/analyse`
- `POST /v1/search/page/validate`
- `POST /v1/search/schema/preview`
- `POST /v1/search/metadata/preview`
- `POST /v1/search/competitor-gap/preview`
- `GET /v1/search/search-console/status`

Preview/analyse endpoints are pure recommendation functions.

Repository-backed GET routes use the `SearchRepository` read-only contract and a stable `search-v1` response envelope. `PostgresSearchRepository` implements that contract with fixed SELECT queries, `SET TRANSACTION READ ONLY`, hard-coded `SET LOCAL ROLE empire_search_reader`, and a required tenant key that is enforced in both SQL and RLS. The default runtime still returns `503 canonical_search_repository_not_activated` instead of fabricated empty data until a real canonical repository/credentials are deliberately activated. Tests can inject a repository without changing production authority, which stabilises the future Search Command Centre contract before database activation.

## Programmatic SEO Policy

Future route families may include:

- `/solutions/[industry]`
- `/services/[service]`
- `/industries/[industry]`
- `/locations/[location]`
- `/compare/[competitor]`
- `/guides/[topic]`
- `/use-cases/[usecase]`
- `/insights/[topic]`
- `/reports/[topic]`

No mass generation or indexing is permitted. No doorway pages, spun content, near-identical city pages or bulk AI filler. Every candidate page must carry differentiated value and pass the quality firewall.

## Search Command Centre

After the backend API contract is stable, build `apps/search-command-centre/` as a Next.js + TypeScript + Tailwind frontend consuming the governed `/v1/search/*` API.

Planned views:
- Organic Revenue / Leads / Conversion;
- indexed, approved and noindex pages;
- quality distribution;
- visibility and CTR;
- top revenue pages and opportunities;
- growing and declining topics/pages;
- technical problems;
- cannibalisation and orphan pages;
- refresh queue and alerts;
- Search Console status;
- metadata/schema/canonical previews.

The frontend is a product surface, not the source of truth. Search rules, attribution and execution authority remain in EmpireOS.

## Next Safe Build Slices

1. Canonical repository/transport ✅ local/tested: stable `search-v1` API repository contract plus tenant-scoped PostgreSQL reader. The staged `empire_search_reader` role is SELECT-only, RLS-enforced by transaction-local `app.tenant_key`, and reached through a transaction-read-only Python transport. The passwordless login shell, production DSN/tenant binding and migration application remain gated.
2. Search Console adapter interface + credential gate ✅ local/tested: `/v1/search/search-console/status` exposes disabled/configured/available state without reading credential contents. Activation remains unavailable until a real adapter and credential approval are separately added.
3. Real SERP snapshot adapter ✅ local/tested: `SearchFabricSerpAdapter` converts only observed Search Fabric results into timestamped provenance-backed snapshots, preserves engine/quality/cache evidence, rejects missing ranking positions instead of inventing them, and reports retrieval failure as unavailable rather than fake success. Runtime network use remains governed by Search Fabric provider health/credentials.
4. Internal-link graph, cannibalisation and content-decay engines ✅ local/tested; deterministic analyzers are covered by focused tests, and the Command Centre now exposes repository-backed decay/cannibalisation technical views without mutation authority.
5. Sitemap/robots/indexation governance engine ✅ local/tested: approved/indexable canonical records can be planned into sitemap groups, while `publish_allowed=false`, `submit_allowed=false` and lifecycle `execution_allowed=false` preserve OBSERVE authority. Repository-driven runtime publication remains separately gated.
6. Evidence-backed competitor gap engine ✅ local/tested: observed SERP snapshots produce Empire coverage, competitor-result presence, content gap, best observed Empire position and competitor domains without inventing keyword volume, traffic, authority or market share. `POST /v1/search/competitor-gap/preview` is OBSERVE-only and projects only observed gap factors into opportunity inputs.
7. Real analytics/session bridge when a canonical first-party analytics model exists.
8. Search Command Centre frontend ✅ foundation local/tested: `apps/search-command-centre/` is a Next.js 16 + TypeScript + Tailwind server-rendered dashboard consuming the governed `search-v1` API through server-only `EMPIRE_SEARCH_API_BASE_URL`. Gated/unavailable metrics remain explicit rather than fabricated. Production deployment/API binding remains gated.
9. Controlled approval/execution layer only after OBSERVE behavior and economics are proven.

## Validation Baseline

Foundation validation must include:
- focused Search Intelligence unit/API tests;
- Python compile checks;
- isolated PostgreSQL migration tests;
- ASGI route registration/health check;
- `git diff --check`;
- no production migration, restart or indexing action.


## Organic + AI Recommendation Intelligence

This is a first-class sellable Search Intelligence product that joins organic
search evidence with captured AI-answer evidence.

Customer question:
"Can buyers discover us in organic search, and when they ask AI systems for
companies like us, are we observed, cited or explicitly recommended?"

Measured outputs:
- organic SERP visibility from real Search Fabric observations;
- observed AI answer presence;
- observed citation presence and source domains;
- observed explicit recommendation presence;
- share of observed recommendations across the monitored brand + competitor set;
- competitor recommendation-gap queries;
- citation/source gaps that can inform content, authority and digital-PR work;
- query portfolios built from real buyer questions;
- search/AI-touch attribution to recognized revenue only where canonical evidence exists.

Truth rules:
- no model preference, hidden ranking or market share may be inferred;
- "share of observed recommendations" is scoped only to the captured answer set;
- no recommendation can be guaranteed;
- missing answer captures remain UNKNOWN rather than zero visibility;
- recommendation/citation observations require timestamped provenance;
- no observed mention, citation or recommendation creates outreach, publishing,
  indexing, payment or commercial execution authority;
- actual revenue remains recognized revenue only.

API foundation:
- `POST /v1/search/recommendation-visibility/preview`
- product key: `organic_ai_recommendation_intelligence`
- mode: OBSERVE
- execution authority: none

The product is designed to combine with Search Console, SERP Intelligence,
AEO/GEO visibility, citation gaps, competitor gaps and Search-to-Revenue
Attribution as those real evidence adapters become available.
