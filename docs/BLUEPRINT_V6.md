# Empire AI — Predictive Revenue OS Blueprint v6

Date: 2026-09-17
Status: CANONICAL CURRENT ROADMAP
Supersedes blueprint_v5.md for current architecture decisions. v5 is retained as history only.

## Mission
Build a governed Predictive Revenue operating system that detects commercial signals, predicts economics, creates demand, acquires and qualifies opportunities, matches buyers, closes revenue, verifies payment, measures profit, learns from outcomes, and reallocates resources through Astra.

## Build Principle
QUALITY → FIRST REVENUE → PROVE ECONOMICS → CAPTURE OUTCOMES → IMPROVE PREDICTIONS → AUTOMATE → SCALE.

## Canonical Architecture Decisions
- Truth/data plane: Supabase project `owbeinlfcfdtwcwrttjy` (Empire-AI Database). SQLite is legacy/cache only.
- Operating coordinator: Astra. Deterministic/local first; premium AI only when economically justified.
- Execution bus: remain OBSERVE until explicit promotion approval.
- Public domain: `empire-ai.co.uk` through Cloudflare Tunnel `Empire-AI`.
- Public gateway: read-only, governed, no settlement/allocation/activation mutation endpoints.
- Agent Web: WebMCP + MCP + A2A share one capability catalogue and governance model.
- Current payment rail: USDT on BNB Smart Chain. Solana/USDC/Phantom/Anchor settlement is retired from active architecture.
- Buyer/payment truth: only independently verified commercial evidence counts as actual revenue.
- Outbound: governed approvals, idempotency, DNC/opt-out/compliance controls.
- Voice: Vonage + ElevenLabs when Conversation OS phase activates.

## Current Live State
- Domain/tunnel restored and reboot-persistent.
- Public Agent Web health, A2A Agent Card and WebMCP manifest live.
- Canonical market intelligence snapshot is Supabase-backed and public-safe/aggregated.
- `market.search`, aggregate `opportunity.search`, and revenue-backed SEO keyword intelligence execute live.
- AEO/GEO/citation schemas are exposed but evidence adapters remain pending; no fabricated visibility claims.
- Astra bootstrap is deterministic/plan-only.
- Autonomous execution service remains OBSERVE.
- BSC payment verification, buyer-payment evidence binding, and separated payment
  proposal/human-approval/verifier roles are deployed fail-closed in canonical Supabase.
- BSC smart-contract escrow database rail is deployed fail-closed; contract mainnet deployment remains gated by external review and production roles.
- Empire Intelligence Fabric schema is being built as the shared temporal/provenance graph across intelligence domains.
- Protected untracked `recovery/` and `toop` remain untouched.

## Cross-Phase Intelligence Fabric — ACTIVE FOUNDATION
The Empire Intelligence Fabric is the shared substrate beneath all intelligence domains. It is not a replacement roadmap phase and does not move the CURRENT marker away from Phase 3F.

Core graph objects:
- canonical companies and people; employment and buying roles; verified contact points
- provenance-backed temporal facts with first/last seen and validity windows
- market, buyer, intent, opportunity, revenue, competitive, pricing, search, AEO/GEO, conversation, risk and governance signals
- TAM segments for software/MRR, high-ticket, managed services, white-label, enterprise and escrow/payment fit
- versioned Omega/Astra scores with confidence, feature evidence and explanations
- offer-fit and expected-value scoring per company
- commercial outcomes for calibration, causal learning and future Digital Twin simulation

Operating rule: intelligence records remain intelligence until a governed qualification step promotes them into CRM/outbound. No crawler, score or model may self-create buyer activation, outreach or settlement.

Moat direction: temporal graph + source provenance + signal fusion + commercial outcomes + causal models + execution history. Every future intelligence engine must read/write through this shared substrate rather than create isolated data silos.

Competitive design target — business-web search plus closed-loop intelligence:
- crawl/index primary business websites directly at internet scale; retain source text and change history
- natural-language ICP, exact-phrase and domain-lookalike search across the company universe
- multilingual company discovery, technographics, domain health and open-web decision-maker discovery
- count-before-materialize queries, exclusions/suppression and confidence floors before CRM promotion
- agent-native API/MCP/SDK access, but all mutation remains governed
- exceed discovery-only platforms with temporal signal sequences, buying-committee reconstruction, multi-offer fit, expected deal value, next-best-action, payment/revenue truth, outcome-conditioned memory and causal learning
- learn from Empire-specific wins/losses/fulfilment/churn/revenue so ranking optimizes for probability of profitable Empire outcomes, not generic ICP similarity alone

## Phase Roadmap

### Phase 0 — Foundation ✅
EmpireOS core, canonical identity, Supabase truth, security controls, execution bus, observability, GitHub/deployment discipline, Cloudflare public gateway.

### Phase 1 — Signal + Acquisition ✅ / Expanding
Satellite Sniper, Storm Tracker, Warehouse Sniper, Market Scanner, Reddit/community intelligence, permits/weather/public data, Source Mesh, OpportunitySignal, entity resolution, quality/provenance, canonical prospect acquisition.

### Phase 2 — Commercial Control Plane ✅
Commercial products, buyer records/capacity, commercial events, fulfilment, idempotency, approval gates, buyer evidence, atomic allocation, activation gate, locked GTM RPCs.

### Phase 3 — First Revenue — IMPLEMENTATION FROZEN / PRODUCTION PROOF GATES CARRIED FORWARD
3A Qualification ✅
3B Market materialization ✅ mostly
3C Canonical acquisition ✅
3D Buyer matching/allocation ✅
3E Governed outbound ✅ implementation complete; production runtime/webhook activation gated
3F Outcome feedback ✅ implementation complete locally; production activation/revenue-proof gates carried forward

Phase 3 no longer blocks later engineering. Its remaining finish line is one genuine governed buyer → agreement → verified payment → delivery → outcome → recognized revenue loop. That proof remains mandatory before expanding consequential commercial authority, but Phase 4/5 may continue in OBSERVE/local-safe modes.

Phase 3E deliverables:
- Buyer discovery from real businesses, not placeholder/public-data pseudo-buyers. Canonical buyer discovery includes business-web evidence, structured Person extraction, decision-maker authority ranking, current-role reconciliation, personhood-quality guards, domain-integrity checks, offer-fit routing, provenance-aware decision-maker-bound contact evidence, hard-bounded batch site review, separate review-ready/outreach-ready contact gates, recent exact public-record/press-release contact provenance, and governed candidate review. The first real outreach-ready buyer has now progressed through production intent creation and human approval; no send has occurred yet.
- Buyer-discovery website evidence now shares the first-party rule with Lead Scoring/Search Fabric: directory/social platform URLs contribute no website score, cannot seed generated work-email patterns, and are never probed as company sites. Accepted `identity_or_direct` acquisition evidence can provide a provenance-preserving first-party website fallback without mutating the canonical prospect row, and canonical first-party evidence wins when present. Public decision-maker evidence is separately fail-closed: official-site role evidence may stand alone, otherwise two independent business-correlated sources must agree on the same person/authority; this never creates contact/outreach authority by itself. An OBSERVE-only buyer-readiness dossier now combines company, decision-maker/contact and existing commercial-activation gates into ordered blockers. All Star Roofing currently reaches corroborated Terry Paris/Owner but remains blocked on a verified person-bound contact, then buyer-record creation. ✅ local/tested
- Governed Resend outbound with approval, idempotency, opt-out and postal-footer compliance. Canonical DB layer + fail-closed Resend provider adapter + dedicated sender transport are live/tested. Outbound Governor policy engine now automates evidence/compliance decisions across OBSERVE, ASSIST and explicitly enabled GUARDED_EXECUTE modes while preserving role-separated approval/send boundaries.
- Reply/provider lifecycle capture. Signed-webhook normalization + per-intent reply alias + exact-sender binding + deterministic reply classification + provider delivery/bounce/complaint/open/click capture are local/tested. Three forward-only DB hardening migrations, reply-ingest credentials, service routing and live webhook enablement remain the final activation work.
- New Supabase-backed AI Closer; legacy SQLite closer execution is retired from active flow. Canonical case/recommendation/human-advance state machine + separated observer/planner/approver runtime identities + OBSERVE-only closer worker are local/tested; canonical migration/credential/service activation remains gated.
- Commercial proposal states without fabricated prices or fake settlement.
- Buyer activation only after verified commercial evidence.
- USDT/BSC payment request + independent on-chain verification.
- First genuine paid buyer recorded as actual revenue in Supabase.

Phase 3F deliverables:
- Append-only delivery outcome, conversion and buyer-satisfaction evidence. ✅ local/tested
- Evidence-derived actual revenue, cost and gross profit from verified BSC direct payment or released escrow only. ✅ local/tested
- Exact approved USD price ↔ USDT settlement invariant; overpayment is not silently counted as revenue. ✅ local/tested
- Canonical feedback projection + Python adapter for Omega/revenue intelligence and Astra priorities. ✅ local/tested
- Hard commercial figures scorecard: actual revenue/cost/gross profit/margin, conversion, buyer satisfaction and buyer/niche profitability via a dedicated read-only role. ✅ local/tested
- OBSERVE-first bounded revenue-recognition worker + systemd timer. ✅ local/tested
- Canonical Lead Intelligence convergence: both lead intake compatibility URLs now feed canonical prospects; evidence-preserving read projection over prospects → acquisition provenance → identity → Intelligence Fabric → qualification is local/tested with a dedicated SELECT-only role. ✅ local/tested
- Read-only canonical-vs-legacy parity engine/CLI is local/tested; it uses only the dedicated Lead Intelligence DSN plus SQLite mode=ro, reports ambiguity/mismatches without reconciling or mutating data. ✅ local/tested
- Lead Intelligence SELECT-only reader role migration is applied in canonical Supabase; runtime credential activation remains gated. Production inspection found 29,807 prospects, 12,184 active identity links, 1,177 qualifications, 466 prospects with both identity + qualification, and only 1 acquisition-ledger row; legacy SQLite crm_leads/lane_leads are empty.
- Intelligence Materializer planner + dedicated append-only writer contract are local/tested: observed prospect facts plus evidence-aware v2 qualification scores (legacy v1 compatibility only), deterministic evidence hashes, v2 confidence sourced from persisted evidence_confidence, unknown dimensions preserved, INSERT-only facts/scores, and no unrelated commercial authority. ✅ local/tested
- Intelligence Materializer schema/role migrations are active in canonical Supabase. One explicitly approved All Star Roofing proof materialized four canonical prospect facts plus one v2 qualification score; runtime credential activation and any bulk historical materialization remain gated. ✅ bounded production proof
- Lead Scoring v2 evidence-aware qualification is local/tested: missing evidence remains unknown instead of zero, directory/social profile URLs cannot count as first-party website evidence, quality and evidence confidence are separated, and low-confidence records become insufficient_evidence. Corrected read-only production inspection shows all 466 identity+qualification prospects still require first-party enrichment: all 466 populated website fields are directory/platform URLs, 164 have phone evidence, none has a first-party website candidate, and the maximum currently observable completeness is 30. ✅ local/tested
- Lead Scoring v2 schema is active in canonical Supabase. One explicitly approved bounded All Star Roofing v2 qualification now coexists with its unchanged v1 row. Buyer allocation now prefers v2 with v1 fallback, independently enforces the v2 evidence-confidence floor, and requires active canonical identity/entity agreement before allocation planning; allocation execution and bulk v2 writes remain gated. ✅ local/tested consumer cutover
- Evidence Enrichment Planner is local/tested: converts v2 confidence gaps into bounded first-party evidence targets, counts only scorer-consumed fields, treats projections as upper bounds, and never performs network work or mutation. ✅ local/tested
- Bounded real-web enrichment execution remains separate from planning; evidence must pass canonical acquisition/Search Fabric discovery + identity guard + site-probe checks before v2 can count it.
- Evidence-backed singleton identity planning is local/tested and fail-closed; it does not relax the bulk duplicate resolver. All Star Roofing (Austin) satisfied accepted direct acquisition provenance + exact phone/name + verified first-party domain corroboration, reached quality 86.3 with decision confidence 0.55, and was explicitly approved for one bounded production entity/link + v2 qualification + Intelligence Fabric projection. Outreach remains production-gated. ✅ bounded production proof
- Supabase production security audit found materially over-broad client grants on legacy/internal public-schema tables. First bounded lockdown slice for b2b_leads, empire_revenue_ledger and legacy crypto_payment_requests is local/tested. A second internal operational/control-plane slice covering agent telemetry/config/task, watcher/healer, pipeline-run and business-action tables is also local/tested. Both revoke anon/authenticated access, enable RLS, preserve service_role/admin access and preserve rows. Production application remains gated.
- Remaining production gates: Intelligence Materializer runtime credential activation and bulk materialization, bulk v2 qualification, security-lockdown migrations, buyer-allocation execution, outbound contact, commercial terms and payment execution.

### Empire Coder — Developer Intelligence Layer (HIGH PRIORITY PARALLEL FOUNDATION)
Empire Coder is the governed internal engineering system for building, debugging, testing, improving and maintaining EmpireOS itself.

Foundation status — local/tested, production activation gated:
- OBSERVE-first capability profile and protected-path/secret-file enforcement.
- Targeted repository intelligence with Blueprint-aware context windows.
- Durable task/plan/checkpoint/proposal state plus versioned compact recovery context for long-running engineering jobs.
- Mandatory best-of-N rule: at least two model candidates -> comparative critique -> synthesized final; first output is never actionable.
- The same best-of-N rule governs proposed next commands before command-policy evaluation.
- Knowledge Garden with canonical precedence, ACTIVE/REVIEW/QUARANTINED states, duplicate/stale guidance detection and active-only default retrieval; Blueprint v6 is the highest roadmap/status authority when canonical sources disagree.
- Provider-agnostic model router with local Ollama support.
- Local qwen3-coder:30b installed and benchmarked on the EmpireOS host; Ollama chat requests explicitly disable model-native thinking because Empire Coder already enforces two-candidate + critique + synthesis reasoning and CPU latency is the bottleneck.
- Read-before-write patching, atomic writes and rollback checkpoints.
- Python AST-aware symbol patching plus dependency/reverse-dependency and impacted-test selection.
- Best-of-N structured patch proposals with strict JSON schema, live-file validation and mandatory revalidation immediately before local application.
- Task-scoped knowledge promotion for REVIEW sources only, with explicit approval, reason, content-hash pinning and automatic invalidation after source changes; QUARANTINED sources remain non-promotable.
- Restricted subprocess runner with filtered environment, timeouts and secret-output scrubbing.
- Specialist Architect/Backend/Frontend/QA/Security/Reviewer role definitions with writer/verifier separation.
- Role-aware model routing now separates `planner`, `writer`, and `verifier`: qwen3-coder:30b is the capability-3 writer + hard-plan fallback; optional qwen2.5-coder:14b is auto-detected as capability-2 planner-only when installed; advisory verification must use a distinct configured provider/model or remain explicitly unavailable. ✅ local/tested routing
- Independent verifier with security, diff and test checks.
- Controlled self-build scope that cannot silently widen authority.
- Staged canonical coder_* Supabase schema with a dedicated least-privilege engineering-state role.
- Localhost-only Ollama systemd packaging is installed and enabled for reboot persistence on the EmpireOS host; an already-healthy pre-existing Ollama process remains undisturbed until reboot.
- Disabled-by-default, internal-token-gated `/v1/coder/*` API for task state and proposal-job queueing only; no remote execution/patch/deploy endpoint.
- Resumable local job queue with stale-job recovery and proposal-only PLAN / NEXT_COMMAND worker.
- Coder worker service/timer is installed and enabled; the timer runs one proposal-only worker pass per minute with localhost-only network access and a 30-minute bounded oneshot start timeout for CPU-local 30B jobs. First live PLAN proof completed with two independent candidates, comparative critique, refined persisted proposal, and zero patch execution. ✅ live governed proof

Candidate engineering changes stop at human approval. Commit/push/merge/deploy, production DB changes, service control, outbound, payment/funds and production credentials remain gated.

### Phase 4 — Astra Operating Layer ← CURRENT
Astra becomes the top coordinator for business priorities, agent routing, bottleneck detection, expected-value decisions, resource allocation, cost control and approval policies. Premium AI is used only when expected value justifies the cost.

Phase 4 observer/calibration implementation status — ✅ local/tested, production activation gated:
1. Astra Observer DB Role ✅ — restricted read-only `empire_astra_observer`; dedicated login remains passwordless/unprovisioned.
2. Astra Role Transport ✅ — locked RPC transport permits only `get_commercial_outcome_feedback(integer)` for the observer role.
3. Outcome Calibration Engine ✅ — real Phase 3F conversion/revenue/cost/gross-profit/satisfaction/repeat-purchase calibration with explicit readiness thresholds.
4. Astra Observer Worker ✅ — bounded feedback read, OBSERVE-only runtime, atomic local snapshot, no fabricated operational counts.
5. Astra Decision Integration ✅ — verified negative-margin outcomes can elevate a review recommendation without changing prices, budgets, model weights or commercial state.
6. Astra Operating Board V1 ✅ — deterministic ranked executive work queue across observed workstreams, preserving approval boundaries and intelligence routing while `decide()` remains backward-compatible through the board's primary item. OBSERVE-only; no execution authority.
7. Phase 4 Test Suite ✅ — Python, isolated PostgreSQL role/permission, fail-closed CLI and systemd verification are green.
8. Runtime Packaging ✅ staged — env template plus `empire-astra-observer.service` / timer exist but are not installed or enabled.
9. Documentation ✅ — `docs/PHASE4_ASTRA_OBSERVER.md`.

Phase 4 authority remains OBSERVE. The canonical Supabase migration, observer credential provisioning and service activation remain production gates. A genuine buyer → verified payment → outcome → feedback loop is still required before Astra receives consequential commercial authority, but it no longer blocks Phase 4 engineering.

### Phase 5 — Organic Growth Engine
SEO, AEO, GEO, keyword intelligence, topic clusters, programmatic pages, AI Cards, citation/mention monitoring, authority/backlink graph, competitor citation gaps, public publishing, first-party tracking and content→revenue attribution.

#### Empire Search Intelligence Engine — PARALLEL FOUNDATION
The proprietary Search Intelligence foundation is being built early in parallel with Phase 3F/4 because it is safe, reversible growth infrastructure and increases product value without bypassing revenue or autonomy gates.

Foundation scope:
- canonical Search Page + Search Opportunity models;
- deterministic opportunity scoring with unknown external metrics left null;
- mandatory Content Quality Firewall;
- metadata, JSON-LD, canonical and indexability recommendations;
- explicit auditable indexation lifecycle;
- OBSERVE-only SearchCommander;
- read-only/recommendation FastAPI surface under `/v1/search/*`, now with a stable `search-v1` repository contract/envelope and fail-closed default when no canonical repository is configured;
- forward-only canonical Supabase schema with tenant/site isolation and search→commercial attribution links; staged least-privilege `empire_search_reader` role + transaction-read-only PostgreSQL repository are local/tested, with RLS tenant scope enforced by `app.tenant_key` and no production credential/application yet;
- Search Console adapter contract + credential/status gate is local/tested and disabled by default; it exposes no credential contents and cannot fetch observations until a real adapter and credential activation are separately approved. Search Fabric-backed SERP snapshots are local/tested as evidence-only adapters: observed ranking positions/provenance are preserved, missing positions are never invented, and failed retrieval remains explicitly unavailable. Evidence-backed competitor gap analysis is also local/tested and derives only observed coverage/presence/gap/best-position/domain signals; broader market metrics stay unknown unless real evidence exists;
- programmatic SEO prohibited from auto-publishing or auto-indexing;
- legacy AEO direct-publish code is compatibility-only and will be governed behind the new layer rather than expanded.

Search Fabric remains the retrieval/discovery substrate. Search Intelligence is the quality, governance, AEO/GEO, opportunity and commercial-attribution layer above it.

Search Command Centre foundation ✅ local/tested: `apps/search-command-centre/` is a Next.js 16 + TypeScript + Tailwind server-rendered dashboard for Organic Revenue, opportunities, page intelligence, alerts and Search Console readiness. A `/technical` drill-down now covers repository-backed indexation, content-decay and cannibalisation evidence. It consumes governed `search-v1` APIs via a server-only API binding, renders gated/unknown states instead of fabricated zeros, and is not the source of truth.

Production database migration, Search Console credentials, sitemap/index submission, content publishing, redirects and robots/canonical mutation remain explicitly gated.

### Phase 6 — A2A Commerce Network
A2A Agent Card/protocol, authenticated agent discovery, agent buyers/suppliers, AI-to-AI quoting, negotiation and tasks, commercial gates, marketplace and revenue attribution. Public discovery stays low-risk; activation/payment/allocation remain governed.

Foundation slice ✅ local/tested: `/a2a/v1/discovery` now publishes machine-readable separation between public read-only capabilities and future authenticated commercial capabilities. Quote/negotiation/task capabilities are discovery-only with authentication + human approval required; execution, payment and allocation remain unexposed.

### Phase 7 — Conversation OS
Vonage, ElevenLabs, streaming voice, barge-in, tone mirroring, summaries/transcripts, AI qualification/closing, human escalation, booking, objections, DISC/coaching, dynamic offers and unified conversation history across email/voice/A2A/CRM.

Foundation slice ✅ local/tested: canonical `empire_conversations` + append-only `empire_conversation_events` are staged as the shared channel-neutral history layer across email/SMS/voice/A2A, linked to existing prospects, entities, buyers, opportunities and closer cases. No provider ingestion writer, Vonage call, ElevenLabs streaming, outbound, booking or production migration is activated.

### Phase 8 — Revenue CRM
Prospect/buyer graph, conversations, pipeline, deal probability, next action, follow-ups, preferences, territory/capacity, offers/contracts/payments, retention, expansion and customer success.

Foundation slice ✅ local/tested: staged read-only `revenue_crm_prospects` and `revenue_crm_buyers` projections compose canonical prospects, Conversation OS, closer state, fulfilment state and buyer activation/capacity. `deal_probability` remains NULL until a calibrated evidence-backed model exists; no follow-up automation, payment action, CRM mutation or production migration is activated.

### Phase 9 — Advertising Brain
Google/Meta integrations, video/ad factory, UGC/avatar creative, A/B testing, media buying, ROAS/profit optimisation, budget allocation, retargeting and landing-page feedback loops.

Foundation slice ✅ local/tested: staged canonical `ad_accounts`, `ad_campaigns`, `ad_creatives` and append-only `ad_performance_observations` provide a measurement spine for spend, attributed revenue, attributed gross profit, clicks, impressions and conversions. ROAS/profit-ROAS stay unknown when attribution is missing; no campaign launch, budget mutation, pause, retargeting or production migration is activated.

### Phase 10 — Predictive Cloud V3
Trend Radar, market/demand/business/buyer/revenue/profit forecasts, churn, LTV, capacity, conversion, Horizon forecasts, Revenue GPS and connected Business/Buyer/Signal/Revenue graphs.

Foundation slice ✅ local/tested: `predictive_cloud_v3` now supports bounded explainable directional forecasts from canonical observed time series only, with a seven-observation minimum gate, explicit trend slope/R²/evidence confidence, and `insufficient_history` instead of guessed direction. Staged forecast/signal tables are read-only to the current service role; no autonomous commercial execution or production migration is activated.

### Phase 11 — Experiment + Causal Engine
Controlled experiments, counterfactuals, holdouts, creative/offer/pricing/page tests, incrementality and causal attribution.

Foundation slice ✅ local/tested: deterministic holdout/treatment assignment planning and append-only experiment outcome observations are staged around the existing `gtm_experiments` model. Incrementality is computed only when each arm has sufficient observed samples; no live traffic mutation, automatic rollout, pricing change or production migration is activated.

### Phase 12 — Demand Genesis
Create demand through content, ads, offers, voice, AEO/GEO, communities, partnerships and agent distribution rather than only harvesting existing demand.

Foundation slice ✅ local/tested: governed demand-plan and evidence records are staged across content/AEO/GEO/community/partnership/agent-distribution/ads/voice channels. Plans require evidence, explicit success metrics and approval, while execution authority is hard-locked to `none`; no publishing, outbound, ad spend, provider activation or production migration is enabled.

### Phase 13 — Revenue Exchange
Inventory marketplace, real-time pricing, exclusives, territories, human/agent buyers, supply-demand pricing, capacity-aware allocation and Revenue Lanes.

Foundation slice ✅ local/tested: staged `revenue_exchange_observations` and a typed exchange snapshot separate inventory/capacity/verified-price intelligence from execution. Supply-demand ratio and observed price ranges are derived only from canonical evidence; allocation, exclusivity enforcement, settlement and production migration remain governed and unexposed.

### Phase 14 — Digital Twin
Simulate markets, campaigns, pricing, buyers, inventory, sales capacity, ad spend and offers before deploying real capital.

Foundation slice ✅ local/tested: deterministic market scenarios now require an observed baseline with provenance plus explicit demand/capacity/price assumptions. Results are permanently labeled `simulation_only=true` and `actual_revenue=false`; no real spend, campaign/pricing mutation or production execution is enabled.

### Phase 15 — Capital Allocator
Astra evaluates expected return, risk, cost, cash, confidence and time-to-revenue to decide where the next unit of capital should go.

### Phase 16 — SaaS / Network Scale
Multi-tenant architecture, teams/RBAC, usage billing, USDT subscriptions, white label, custom domains, affiliate/agency/client dashboards, API keys, developer platform and marketplace/partner network.

### Phase 17 — Enterprise
Auditability, permissions/data isolation, SLA/compliance/security monitoring, backup/DR, multi-region, Kubernetes, Kafka, ClickHouse/Grafana, queues, model registry and retraining when justified by real load.

### Phase 18 — Full Autonomous Revenue OS
Astra detects → predicts economics → selects market → creates acquisition/content/ads → finds buyers → runs conversations → closes → verifies payment → delivers → measures actual profit → learns → reallocates.

## Retain and Upgrade
- Cinematic Landing, Truth Portal, Ghost Ledger privacy concepts, Hall of Fame, Sniper Leaderboard, Live Strike Zone and Partner Network.
- Self-improving landing pages, Whale Hunter, Storm Chaser, Satellite Scout, high-ticket cinematic demos and pay-per-call.
- Partner/affiliate, done-for-you ads + SEO, agency white-label and private-data/whale-data concepts.
- Treasury/commercial proof, on-chain verification, crypto billing and agent commerce — upgraded onto current USDT/BSC + governed architecture.
- Hermes remains useful as a specialist agent/prompt layer; Astra is the operating coordinator above agents.

## Retire from Active Architecture
- Solana/USDC/Phantom/Anchor/Solana Pay/Helius settlement paths.
- Legacy SQLite as business source of truth.
- Legacy AI closer behaviour that invents settlement amounts or changes funnel states without evidence.
- Simulated/fabricated settlement, fake revenue and placeholder buyer activation.
- Legacy synthetic runtime augmentation, finance replay, autonomous funnel mutation and mock marketplace settlement are retired/fail-closed.
- Direct public access to allocation, activation, settlement, treasury or campaign mutation endpoints.

## Infrastructure Gated Until Economically Justified
Docker/Kubernetes, Kafka, Redis/queues, ClickHouse/Grafana, multi-region deployment, heavy model-serving infrastructure and continuous retraining remain later-stage tools. They activate only when measured scale, reliability or revenue requirements justify the complexity.

## Immediate Execution Order
1. Complete canonical Lead Intelligence convergence and security prerequisites: keep the dedicated reader/runtime identities least-privilege, apply only reviewed Supabase lockdown slices, then activate the Intelligence Materializer on bounded real prospects before any bulk historical write.
2. Activate the staged Phase 3E outbound/reply hardening migrations and inbound runtime under the existing production gates.
3. Activate Phase 3F outcome/revenue migration and dedicated runtime identities in OBSERVE first.
4. Send/deliver the first genuine governed buyer opportunity and capture real delivery/conversion evidence.
5. Recognize the first independently verified paid outcome as actual revenue and gross profit.
6. Feed the canonical Phase 3F outcome projection into Astra/Omega/revenue intelligence calibration.
7. Supabase-backed AI Closer production state-machine gate ✅ local/tested; activate its canonical migrations, separated runtime credentials and OBSERVE worker only under production gates.
8. Phase 4 Astra Operating Layer is CURRENT in OBSERVE/local-safe engineering mode; carry the first-revenue feedback loop as a production authority gate rather than an engineering blocker.
9. Continue Phase 5 organic intelligence and Phase 6 Agent Web/A2A capability execution in parallel where they do not bypass gates. Build the Search Intelligence foundation first; stabilize its API contract, then build the Search Command Centre frontend.
10. Expand Astra operating authority only after the genuine buyer → verified payment → outcome → feedback loop proves controls and economics.

11. BSC USDT smart-contract escrow: local contract + verifier + database rail ✅;
    canonical Supabase migration ✅; external audit, production identities and mainnet contract deployment pending.
12. Empire Intelligence Fabric: canonical schema + provenance/temporal graph ← ACTIVE SUPPORT WORK;
    integrate real source adapters and TAM segmentation while primary effort completes Phase 3F outcome/revenue feedback.

## Definition of Actual Revenue
Actual revenue requires independently verifiable payment evidence tied to a real buyer, real commercial terms and the relevant Empire request/order. Escrow funding is not revenue; a verified escrow release is only revenue-eligible until a separate governed accounting event recognizes it. Modeled, forecast, quoted, pending, simulated or manually asserted values are not actual revenue.
