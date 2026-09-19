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

### Phase 3 — First Revenue ← CURRENT
3A Qualification ✅
3B Market materialization ✅ mostly
3C Canonical acquisition ✅
3D Buyer matching/allocation ✅
3E Governed outbound ✅ implementation complete; production runtime/webhook activation gated
3F Outcome feedback ← NOW (implementation complete locally; production activation gated)

Phase 3E deliverables:
- Buyer discovery from real businesses, not placeholder/public-data pseudo-buyers. Canonical buyer discovery includes business-web evidence, structured Person extraction, decision-maker authority ranking, current-role reconciliation, personhood-quality guards, domain-integrity checks, offer-fit routing, provenance-aware decision-maker-bound contact evidence, hard-bounded batch site review, separate review-ready/outreach-ready contact gates, recent exact public-record/press-release contact provenance, and governed candidate review. The first real outreach-ready buyer has now progressed through production intent creation and human approval; no send has occurred yet.
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
- Lead Intelligence reader-role migration/credential activation, production parity execution, internal API exposure, and legacy CRM consumer migration remain gated.
- Production migration/runtime credential activation and live evidence observation remain gated.

### Empire Coder — Developer Intelligence Layer (HIGH PRIORITY PARALLEL FOUNDATION)
Empire Coder is the governed internal engineering system for building, debugging, testing, improving and maintaining EmpireOS itself.

Foundation status — local/tested, production activation gated:
- OBSERVE-first capability profile and protected-path/secret-file enforcement.
- Targeted repository intelligence with Blueprint-aware context windows.
- Durable task/plan/checkpoint/proposal state plus versioned compact recovery context for long-running engineering jobs.
- Mandatory best-of-N rule: at least two model candidates -> comparative critique -> synthesized final; first output is never actionable.
- The same best-of-N rule governs proposed next commands before command-policy evaluation.
- Knowledge Garden with canonical precedence, ACTIVE/REVIEW/QUARANTINED states, duplicate/stale guidance detection and active-only default retrieval.
- Provider-agnostic model router with local Ollama support.
- Local qwen3-coder:30b installed and benchmarked on the EmpireOS host.
- Read-before-write patching, atomic writes and rollback checkpoints.
- Python AST-aware symbol patching plus dependency/reverse-dependency and impacted-test selection.
- Best-of-N structured patch proposals with strict JSON schema, live-file validation and mandatory revalidation immediately before local application.
- Task-scoped knowledge promotion for REVIEW sources only, with explicit approval, reason, content-hash pinning and automatic invalidation after source changes; QUARANTINED sources remain non-promotable.
- Restricted subprocess runner with filtered environment, timeouts and secret-output scrubbing.
- Specialist Architect/Backend/Frontend/QA/Security/Reviewer role definitions with writer/verifier separation.
- Role-aware model routing: local qwen3-coder:30b is writer-only by default; advisory model verification must use a distinct configured provider/model or remain explicitly unavailable.
- Independent verifier with security, diff and test checks.
- Controlled self-build scope that cannot silently widen authority.
- Staged canonical coder_* Supabase schema with a dedicated least-privilege engineering-state role.
- Staged localhost-only Ollama systemd packaging; not installed/enabled automatically.
- Disabled-by-default, internal-token-gated `/v1/coder/*` API for task state and proposal-job queueing only; no remote execution/patch/deploy endpoint.
- Resumable local job queue with stale-job recovery and proposal-only PLAN / NEXT_COMMAND worker.
- Staged Coder worker service/timer with localhost-only network access; not installed/enabled automatically.

Candidate engineering changes stop at human approval. Commit/push/merge/deploy, production DB changes, service control, outbound, payment/funds and production credentials remain gated.

### Phase 4 — Astra Operating Layer
Astra becomes the top coordinator for business priorities, agent routing, bottleneck detection, expected-value decisions, resource allocation, cost control and approval policies. Premium AI is used only when expected value justifies the cost.

Phase 4 observer/calibration implementation status — ✅ local/tested, production activation gated:
1. Astra Observer DB Role ✅ — restricted read-only `empire_astra_observer`; dedicated login remains passwordless/unprovisioned.
2. Astra Role Transport ✅ — locked RPC transport permits only `get_commercial_outcome_feedback(integer)` for the observer role.
3. Outcome Calibration Engine ✅ — real Phase 3F conversion/revenue/cost/gross-profit/satisfaction/repeat-purchase calibration with explicit readiness thresholds.
4. Astra Observer Worker ✅ — bounded feedback read, OBSERVE-only runtime, atomic local snapshot, no fabricated operational counts.
5. Astra Decision Integration ✅ — verified negative-margin outcomes can elevate a review recommendation without changing prices, budgets, model weights or commercial state.
6. Phase 4 Test Suite ✅ — Python, isolated PostgreSQL role/permission, fail-closed CLI and systemd verification are green.
7. Runtime Packaging ✅ staged — env template plus `empire-astra-observer.service` / timer exist but are not installed or enabled.
8. Documentation ✅ — `docs/PHASE4_ASTRA_OBSERVER.md`.

Phase 4 authority remains OBSERVE. The canonical Supabase migration, observer credential provisioning and service activation remain production gates. The CURRENT roadmap marker stays on Phase 3F until a genuine buyer → verified payment → outcome → feedback loop is proven end to end.

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
- read-only/recommendation FastAPI surface under `/v1/search/*`;
- forward-only canonical Supabase schema with tenant/site isolation and search→commercial attribution links;
- Search Console/SERP adapters disabled until real evidence/credentials exist;
- programmatic SEO prohibited from auto-publishing or auto-indexing;
- legacy AEO direct-publish code is compatibility-only and will be governed behind the new layer rather than expanded.

Search Fabric remains the retrieval/discovery substrate. Search Intelligence is the quality, governance, AEO/GEO, opportunity and commercial-attribution layer above it.

After the API contract is stable, add a Next.js + TypeScript + Tailwind Search Command Centre for Organic Revenue, opportunities, page quality, indexation, decay, cannibalisation, alerts, Search Console and metadata/schema previews. The UI consumes governed APIs and is not the source of truth.

Production database migration, Search Console credentials, sitemap/index submission, content publishing, redirects and robots/canonical mutation remain explicitly gated.

### Phase 6 — A2A Commerce Network
A2A Agent Card/protocol, authenticated agent discovery, agent buyers/suppliers, AI-to-AI quoting, negotiation and tasks, commercial gates, marketplace and revenue attribution. Public discovery stays low-risk; activation/payment/allocation remain governed.

### Phase 7 — Conversation OS
Vonage, ElevenLabs, streaming voice, barge-in, tone mirroring, summaries/transcripts, AI qualification/closing, human escalation, booking, objections, DISC/coaching, dynamic offers and unified conversation history across email/voice/A2A/CRM.

### Phase 8 — Revenue CRM
Prospect/buyer graph, conversations, pipeline, deal probability, next action, follow-ups, preferences, territory/capacity, offers/contracts/payments, retention, expansion and customer success.

### Phase 9 — Advertising Brain
Google/Meta integrations, video/ad factory, UGC/avatar creative, A/B testing, media buying, ROAS/profit optimisation, budget allocation, retargeting and landing-page feedback loops.

### Phase 10 — Predictive Cloud V3
Trend Radar, market/demand/business/buyer/revenue/profit forecasts, churn, LTV, capacity, conversion, Horizon forecasts, Revenue GPS and connected Business/Buyer/Signal/Revenue graphs.

### Phase 11 — Experiment + Causal Engine
Controlled experiments, counterfactuals, holdouts, creative/offer/pricing/page tests, incrementality and causal attribution.

### Phase 12 — Demand Genesis
Create demand through content, ads, offers, voice, AEO/GEO, communities, partnerships and agent distribution rather than only harvesting existing demand.

### Phase 13 — Revenue Exchange
Inventory marketplace, real-time pricing, exclusives, territories, human/agent buyers, supply-demand pricing, capacity-aware allocation and Revenue Lanes.

### Phase 14 — Digital Twin
Simulate markets, campaigns, pricing, buyers, inventory, sales capacity, ad spend and offers before deploying real capital.

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
1. Complete canonical Lead Intelligence convergence: prove parity, provision the dedicated reader identity under the production gate, and migrate legacy lead consumers incrementally without creating another lead database.
2. Activate the staged Phase 3E outbound/reply hardening migrations and inbound runtime under the existing production gates.
3. Activate Phase 3F outcome/revenue migration and dedicated runtime identities in OBSERVE first.
4. Send/deliver the first genuine governed buyer opportunity and capture real delivery/conversion evidence.
5. Recognize the first independently verified paid outcome as actual revenue and gross profit.
6. Feed the canonical Phase 3F outcome projection into Astra/Omega/revenue intelligence calibration.
7. Supabase-backed AI Closer production state-machine gate ✅ local/tested; activate its canonical migrations, separated runtime credentials and OBSERVE worker only under production gates.
8. Move the CURRENT marker to Phase 4 Astra Operating Layer once first-revenue feedback is proven end to end.
9. Continue Phase 5 organic intelligence and Phase 6 Agent Web/A2A capability execution in parallel where they do not bypass gates. Build the Search Intelligence foundation first; stabilize its API contract, then build the Search Command Centre frontend.
10. Expand Astra operating authority only after proven controls and economics.

11. BSC USDT smart-contract escrow: local contract + verifier + database rail ✅;
    canonical Supabase migration ✅; external audit, production identities and mainnet contract deployment pending.
12. Empire Intelligence Fabric: canonical schema + provenance/temporal graph ← ACTIVE SUPPORT WORK;
    integrate real source adapters and TAM segmentation while primary effort completes Phase 3F outcome/revenue feedback.

## Definition of Actual Revenue
Actual revenue requires independently verifiable payment evidence tied to a real buyer, real commercial terms and the relevant Empire request/order. Escrow funding is not revenue; a verified escrow release is only revenue-eligible until a separate governed accounting event recognizes it. Modeled, forecast, quoted, pending, simulated or manually asserted values are not actual revenue.
