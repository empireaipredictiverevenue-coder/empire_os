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
The Empire Intelligence Fabric is the shared substrate beneath all intelligence domains. It is not a replacement roadmap phase and does not move the CURRENT marker away from Phase 3E.

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
3E Governed outbound ← NOW (canonical DB layer local/tested)
3F Outcome feedback

Phase 3E deliverables:
- Buyer discovery from real businesses, not placeholder/public-data pseudo-buyers.
- Governed Resend outbound with approval, idempotency, opt-out and postal-footer compliance. Canonical intent/approval/send/reply/suppression DB layer local + tested; provider adapter deployment pending.
- Reply capture and classification. Canonical reply ingest/classification/suppression DB layer local + tested; live provider webhook pending.
- New Supabase-backed AI Closer; legacy SQLite closer is retired from active flow.
- Commercial proposal states without fabricated prices or fake settlement.
- Buyer activation only after verified commercial evidence.
- USDT/BSC payment request + independent on-chain verification.
- First genuine paid buyer recorded as actual revenue in Supabase.

Phase 3F deliverables:
- Delivery outcome, conversion, actual revenue, cost, gross profit and buyer satisfaction.
- Feed actual outcomes back into Omega/revenue intelligence and Astra priorities.

### Phase 4 — Astra Operating Layer
Astra becomes the top coordinator for business priorities, agent routing, bottleneck detection, expected-value decisions, resource allocation, cost control and approval policies. Premium AI is used only when expected value justifies the cost.

### Phase 5 — Organic Growth Engine
SEO, AEO, GEO, keyword intelligence, topic clusters, programmatic pages, AI Cards, citation/mention monitoring, authority/backlink graph, competitor citation gaps, public publishing, first-party tracking and content→revenue attribution.

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
- Direct public access to allocation, activation, settlement, treasury or campaign mutation endpoints.

## Infrastructure Gated Until Economically Justified
Docker/Kubernetes, Kafka, Redis/queues, ClickHouse/Grafana, multi-region deployment, heavy model-serving infrastructure and continuous retraining remain later-stage tools. They activate only when measured scale, reliability or revenue requirements justify the complexity.

## Immediate Execution Order
1. Complete Phase 3E governed buyer outbound/reply capture.
2. Replace legacy AI Closer with Supabase-backed commercial state machine.
3. Fail-closed USDT/BSC verifier, evidence adapter, and governed request/approval
   separation ✅
4. Provision controlled operator-approval and verifier service identities/tools without
   exposing public mutation or granting agents self-approval. Local/manual tooling ✅;
   production login identities remain a deployment gate.
5. Activate first genuine buyer only after verified evidence.
6. Deliver first paid opportunity and capture outcome/profit.
7. Feed actual outcomes into Astra/Omega/revenue intelligence.
8. Continue Phase 5 organic intelligence and Phase 6 Agent Web/A2A capability execution.
9. Expand Astra operating authority only after proven controls and economics.

10. BSC USDT smart-contract escrow: local contract + verifier + database rail ✅;
    canonical Supabase migration ✅; external audit, production identities and mainnet contract deployment pending.
11. Empire Intelligence Fabric: canonical schema + provenance/temporal graph ← ACTIVE SUPPORT WORK;
    integrate real source adapters and TAM segmentation, then return primary effort to Phase 3E outbound/reply capture.

## Definition of Actual Revenue
Actual revenue requires independently verifiable payment evidence tied to a real buyer, real commercial terms and the relevant Empire request/order. Escrow funding is not revenue; a verified escrow release is only revenue-eligible until a separate governed accounting event recognizes it. Modeled, forecast, quoted, pending, simulated or manually asserted values are not actual revenue.
