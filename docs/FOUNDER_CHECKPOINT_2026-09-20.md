# EmpireOS Founder Checkpoint — 2026-09-20

## Canonical production state
- Repo: /srv/empire_os
- Branch: feature/revenue-intelligence-v2
- Canonical DB: Supabase owbeinlfcfdtwcwrttjy
- Payment rail: USDT on BSC
- Execution: governed; no synthetic production data; unknown remains unknown
- Protected: /srv/empire_os/recovery/ and /srv/empire_os/toop
- Git rule: explicit paths only; never git add .

## Current architecture
EmpireOS is an intelligence and revenue operating system. Scrapers/snipers are sensors, not the product.
Commercial intelligence is organized into nodes feeding a shared Intelligence Fabric.

## Intelligence Nodes
Home Services, Property Opportunity, Market Intent, Corporate Change,
Government Spend, Healthcare Growth, Compliance & Risk, Legal & Mass Tort.

## Acquisition
Adaptive diversified acquisition policy committed in 2265520.
Families: coverage, intent, property/regulatory, event/disaster.
Registered real keyless sources include overpass, biz_search, reddit, permits,
chicago_311, courtlistener, nyc_hpd and nws_alerts.

## Legal / Mass Tort recovery
- Node restored in commit b6c4e73.
- Existing assets: firm_finder, firm_import, firm_sources manifest, mass_tort_agent,
  CA/TX bar source definitions, CourtListener, Reddit mass-tort intelligence,
  Search Fabric, adgen scanner, legal AEO pages and Mass Tort Intake campaign code.
- Identity reconciliation runtime contains 547 legal candidate rows across
  522 unique firm names: 122 mass tort, 213 personal injury, 78 class action,
  73 medical malpractice and 61 workers comp.
- These 547 are candidate/dry-run intelligence, not automatically canonical live prospects.
- Next legal step: reconcile/promote only verified canonical firms into the live Intelligence Fabric.

## Current live operating constraints
- Email outbound daily cap remains 10 unless founder explicitly expands it.
- Phone/Vonage deferred for later; no live-call authority.
- Internal crawl, enrichment, qualification, intelligence and proposal work may continue automatically.
- No revenue is declared without verified payment/revenue evidence.

## Current commercial bottleneck
Raw business supply is healthy. Decision-maker identity/contact recovery remains important.
Deferred unresolved buyers stay eligible for repeated first-party enrichment rather than being failed.

## Parallel build lanes
1. Legal/Mass Tort canonical recovery: map legacy/runtime firm candidates to canonical entities without inventing or overwriting evidence.
2. Founder Console: surface intelligence nodes, source health, data products and opportunity counts without touching live authority controls.
3. Data Products/API: define node product contracts and read-only export surfaces for sellable intelligence products.

## Recent commits
- 2265520 feat(acquisition): diversify source families adaptively
- 7b8cc3f feat(intelligence): define commercial intelligence nodes
- b6c4e73 feat(intelligence): restore legal mass tort node

## Founder directive
Move fast. Do not stop for reversible engineering decisions.
Do not duplicate existing systems. Preserve concurrent work.
Only stop at genuine founder gates: destructive/irreversible changes, fund movement,
legally binding acceptance, irreversible accounting/revenue recognition, or authority expansion.

## Roadmap execution order updated
Blueprint v6 now contains a Founder Execution Lock dated 2026-09-20.

Active priorities only:
1. Prove the genuine commercial revenue loop.
2. Productize the Intelligence Fabric / Intelligence Nodes.
3. Build Founder Console operating visibility.

Everything else is parked unless it directly unblocks one of those three.
Parallel coder work must map to Priority 1-3 and may not create a new roadmap branch.

## Node expansion
Solar & Energy and HVAC & Climate Services are now first-class Intelligence Nodes under Priority 2.
They are not separate roadmap branches; they reuse the shared acquisition, property, weather,
registry, Search Fabric and canonical Intelligence Fabric foundations.

## Predictive market + Deal Room expansion
Roadmap now includes:
- 30/90 day and 6/12/18/24 month evidence-backed forecasts;
- trend velocity/acceleration, structural breaks and market-regime detection;
- current-vs-future industry operating-model intelligence;
- forecast-vs-actual calibration through Omega/Astra;
- one Deal Room backbone for human and A2A commerce;
- Documenso adapter for agreement envelopes, embedded signing and verified lifecycle webhooks;
- A2A v1.0 conformance review and commercial task/artifact alignment.

Binding agreement send/sign/acceptance remains a founder/commercial gate.

## Trust / reputation baseline
Trust & Reputation is now a cross-cutting Priority 1-3 capability.

Observed public baseline:
- HTTPS live behind Cloudflare.
- CSP present.
- X-Content-Type-Options nosniff present.
- X-Frame-Options DENY present.
- Referrer-Policy strict-origin-when-cross-origin present.
- SPF exists and includes multiple current/historical sender providers.
- DMARC exists but is monitoring-only (p=none).
- HSTS not currently advertised.
- Permissions-Policy not currently advertised.

Trust build direction:
- internal evidence-backed Trust Readiness Score only;
- public Trust Center shows evidence, not a self-awarded score;
- validate SPF lookup budget and retire obsolete senders before DMARC enforcement;
- move DMARC from monitor -> staged enforcement only after sender verification;
- review HSTS/Permissions-Policy safely before activation;
- publish clear company identity, contact, privacy/security and commercial-process proof;
- add only genuine signed-deal, payment, delivery, outcome, reference and case-study evidence as it is observed.

## Search / AEO / GEO recovery status
Phase 5 foundation was already completed locally/tested in earlier phases.
Current work is recovery/convergence, not a rebuild.
The old Vultr shutdown removed the disk-backed /srv/aeo deployment and sitemap artifacts.
The repo still contains 210 generated legacy AEO pages across 42 niches plus the governed
Search Intelligence engine, Search Command Centre, GEO/AI citation analysis, sitemap/robots
planning, backlink/citation-gap, indexation, cannibalisation and content-decay modules.
New work must reconnect/recover those assets under the canonical Search Intelligence layer.

## Supabase security audit
Current Supabase inspection reported 115 legacy/public tables with RLS disabled.
Do not blindly enable RLS: missing policies could break production access.
A dedicated coder lane is performing a read-only dependency/policy audit and staged remediation proposal.

## AEO historical count correction
Do not treat 210 as the historical total.
210 = surviving Git/tarball metro-page batch.
Historical code also records 308 AEO pages in use; prior runtime archaeology found other deployed/indexed snapshots.
The full old Vultr /srv/aeo estate count is currently unknown. Founder recalls 3,000+ pages; preserve that as an unverified historical lead until archival/runtime evidence confirms or disproves it.

## Private capital / roll-up expansion
Private Capital & Roll-Up is now a first-class Intelligence Node.
It connects sponsor/adviser identity, portfolio companies, M&A announcements, public registries,
property/operating signals and Search Fabric into sponsor graphs, roll-up maps, add-on target feeds,
founder-exit signals, portfolio-growth opportunities and consolidation intelligence.
Premium public industry pages now include Private Equity alongside Property, Solar, HVAC, Roofing
and Legal/Mass Tort.

## Buyer identity recovery hardening
Added official public-license identity seeds for evidence-first buyer recovery.
Initial production source: Texas State Board of Plumbing Examiners Responsible Master Plumber daily CSV.
License records provide a named professional/company association only; they do not establish buyer authority.
Empire still requires first-party site evidence for a commercial decision role before promotion.
Live testing caught and fixed a PATRIOT/RIOT fuzzy-match false positive before promotion.
