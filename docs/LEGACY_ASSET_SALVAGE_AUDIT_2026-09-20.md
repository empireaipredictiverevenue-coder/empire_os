# Legacy Asset Salvage Audit — 2026-09-20

Sources reviewed:
- Steps to Deploy and Run Neural Scout (1).zip
- How to Generate Roofing Leads with Professional Outreach.zip

Purpose: recover useful architecture, workflows, UI ideas and GTM patterns without reintroducing fake data, stale payment rails, duplicate agents or obsolete infrastructure.

## Executive verdict

Do NOT restore either archive wholesale.

The Neural Scout archive is a valuable component mine, but contains substantial duplication, legacy Solana/USDC/Vapi/Twilio assumptions, JSON-file persistence, mock/synthetic data, and old architecture now superseded by canonical Supabase, BSC/USDT, Vonage, Revenue Truth, Quant Brain, AGI Control, Search Intelligence and Empire Ops MCP.

The roofing outreach archive is useful mainly for positioning/cadence. Several contact lists contain placeholder/555-style phone numbers and are stale June-2026 snapshots. Treat every contractor/contact as unverified until re-discovered and re-enriched through the live canonical pipeline.

## Archive inventory

Neural Scout pack:
- 253 files before recursive nested extraction
- Python, TypeScript/TSX, SQL, Markdown, JSON, nested ZIPs, PDF, dashboards and deployment material
- 85 exact duplicate groups after nested extraction
- major duplicate set comes from the embedded Empire Omega complete export

Roofing outreach pack:
- 22 files
- almost entirely Markdown/templates
- 8 obvious 555-style numbers in the old comprehensive lead list
- useful positioning and follow-up patterns, but not canonical lead evidence

## KEEP / REBUILD CLEANLY

### 1. Continuous outcome-learning loop
Legacy sources:
- AI_LEARNING_SYSTEM.md
- server/routers/ai-learning.ts
- server/ai-engine/index.ts
- empire_si_strategy.py

Useful ideas:
- closed-loop learning from outcomes
- strategy comparison/evolution
- parameter tuning from actual results
- multi-touch workflow selection
- lead-quality feedback

Current Empire mapping:
- outcome_feedback.py
- revenue_os_feedback.py
- revenue_os_learning.py
- astra_feedback.py
- Quant Brain
- Experiment/Causal layer

Action:
Rebuild only against verified Revenue Truth. Never learn from model-generated revenue, synthetic conversions or fallback estimates.

### 2. Evidence-backed content intelligence
Legacy sources:
- content_engine.py
- data-magnet / statistic-cluster / monster-post concepts

Useful ideas:
- statistic clusters
- authority/monster posts
- citation hooks
- content generated from proprietary market intelligence
- content tied to commercial verticals

Current Empire mapping:
- Marketing Department
- Search Intelligence
- SEO/AEO/GEO strategy
- Keyword Universe
- R&D/Market Intelligence

Action:
Rebuild with mandatory source/provenance/freshness for every statistic and claim. No invented revenue-leak numbers.

### 3. Fast inbound response
Legacy source:
- realtime_webhook.py

Useful ideas:
- respond quickly to genuine first-party inbound intent
- enrich -> qualify -> route -> conversation
- event-driven rather than batch-only

Reject:
- Vapi
- Flask/JSON lead persistence
- unconditional auto-calling

Action:
Rebuild on canonical Supabase + Vonage + Conversation OS + governed reply/closer state. Target sub-60-second response where policy permits.

### 4. Campaign/strategy evolution
Legacy sources:
- empire_si_strategy.py
- campaign/outreach automation modules
- adaptive parameter concepts

Useful ideas:
- competing strategies
- measurable outcomes
- per-niche/per-territory adaptation
- frequency/cadence parameter tuning

Action:
Integrate into Experiment/Causal + Quant Brain. Promote only from verified outcome evidence.

### 5. Founding Partner / pay-per-call GTM
Legacy sources:
- Empire AI Final Lead Generation and Outreach Summary.md
- empire_ai_founding_partner_outreach.md
- follow-up templates

Useful framing:
- founding partner
- territory/city focus
- pay-per-qualified-call
- priority/exclusivity when genuinely available
- no large upfront fee
- capacity-oriented CTA

Required rewrite:
- all claims must be current and evidenced
- no fake scarcity
- no unverified NOAA/storm claims
- clear qualification definition
- opt-out/compliance
- fresh verified contact identity

Current Empire mapping:
- Commercial Blueprint
- territory/corridor seats
- governed outbound
- buyer capacity
- Revenue CRM / AI Closer

### 6. Analytics / ROI UI patterns
Legacy sources:
- MarketSweepAnalyticsDashboard.tsx
- ROICalculator.tsx
- AuditDashboard.tsx
- advanced_analytics.py

Useful ideas:
- revenue-impact visualisation
- conversion/ROI drill-down
- market sweep heatmaps
- audit evidence display

Action:
Reuse design concepts only. Bind UI to canonical observed metrics, not legacy estimates.

### 7. Secure database/MCP patterns
Legacy sources:
- mcp-database-server.py
- si_mcp_bridge.py
- PHASE2_MCP_BRIDGE_DEPLOYMENT.md

Useful ideas:
- narrow DB bridge
- read-only-by-default
- query auditing
- tool-specific access rather than general shell

Current Empire mapping:
- Empire Ops MCP
- Agent Web / WebMCP / A2A
- Supabase role transports

Action:
Concept already superseded. Use only as design-reference while expanding Empire Ops MCP.

### 8. Affiliate / usage / pricing concepts
Legacy source:
- monetization.py

Useful ideas:
- tiers
- usage allowances
- annual discounts
- affiliate revenue sharing
- invoicing
- white-label packaging

Reject implementation:
- SOL/USDC rails
- local JSON subscription state
- hard-coded SOL pricing

Action:
Translate concepts into current BSC/USDT + canonical commercial terms + SaaS packaging only if supported by actual pricing strategy.

## SUPERSEDED — DO NOT MERGE DIRECTLY

- old Solana payment modules
- Phantom/Anchor/Jupiter settlement logic
- Vapi calling modules
- Twilio-specific flows
- JSON-file lead stores
- old Flask webhook stack
- old CRM sync implementations
- old AI-learning router with embedded mock leads
- old MCP bridge implementation
- old Omega agent architecture where current AGI/Quant/Astra systems already supersede it
- Kubernetes/Incus/Coolify deployment recipes unless a current infra decision specifically needs them

## REJECT / QUARANTINE

### Synthetic or unverifiable market data
Examples:
- global_market_data.json
- old market sweep exports/reports
- files containing hard-coded 555 contacts
- mock lead arrays
- example Acme/test buyers
- seed data represented as operating evidence

Allowed use:
test fixtures or UI demos only when explicitly labelled synthetic.

### Outcome marketing fallbacks
Legacy outcome_marketing.py falls back to invented dollar leak estimates when the model call fails.

Reject this behavior completely.

Unknown must remain unknown.

### Legacy payment evidence
Old Solana/USDC whale/onboarding/payment listener material is not compatible with canonical BSC/USDT Revenue Truth.

Do not restore.

## SECURITY HANDLING

The archive contains many files with secret-like configuration patterns and environment/API-key placeholders.

Rules:
- never commit the raw archive into the EmpireOS repo
- never copy .env/config values blindly
- never display or reuse unknown historical credentials
- treat old credentials as potentially compromised/expired
- create fresh least-privilege credentials when a legacy integration is intentionally revived

## Roofing outreach pack — specific ruling

Useful:
- founding-partner framing
- pay-per-call language
- short CTA
- follow-up cadence
- storm-specialist ICP concept
- capacity question

Do not trust:
- June 2026 lead/contact lists
- 555-style entries
- statements that outreach was sent
- old storm event claims without fresh verification
- exclusivity claims unless inventory/territory state proves them

All companies must flow through:
real source -> canonical prospect -> first-party enrichment -> person/contact verification -> governed outreach readiness.

## Top integration queue

1. Outcome/strategy learning from verified outcomes
2. Evidence-backed proprietary content engine
3. Sub-60-second inbound response workflow
4. Roofing founding-partner GTM packet using fresh evidence
5. ROI/market analytics UI patterns
6. Pricing/affiliate concepts mapped to current commercial architecture

Empire Coder PLAN jobs created for the first four items.

## Non-negotiable

No fake data.
No synthetic production evidence.
No fallback dollar claims.
No legacy Solana/USDC settlement.
No Vapi/Twilio regression.
No raw archive code copied into production without review/tests.
