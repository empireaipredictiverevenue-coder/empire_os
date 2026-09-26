# GTM Swarm / Agency Revenue Engine Salvage — 2026-09-20

This note reconciles two historical Empire AI blueprints with the current
Blueprint v6 architecture. Historical documents are design evidence only;
they do not override current production truth or governance.

## Adopt now

### Multi-niche GTM configuration
Use one governed GTM system with per-niche configuration rather than separate
ad-hoc agents. Canonical implementation: `empire_os/gtm_swarm_v6.py`.

Per-niche configuration includes:
- niche / ICP;
- target metros;
- evidence-backed qualification threshold;
- allowed channels;
- preferred micro lead magnets;
- canonical outbound-governor handoff.

### Intent-based micro lead magnets
Retain the three strong concepts:
1. Revenue / Performance Leak Audit.
2. Live Event / Disruption Radar.
3. Competitor Stack & Cost Replacement Calculator.

Selection is based on observed intent and event evidence. No lead magnet claims
price, ROI or market economics without evidence.

### Niche tiers and high-ticket offer strategy
Retain the business segmentation:
- Tier 1: roofing and restoration as canonical high-ticket launch verticals.
- Tier 2: other high-cash-flow / PE-backed operations only when evidence exists.
- Tier 3: founder-network/domain-fit verticals where real advantage exists.

Canonical implementation: `empire_os/gtm_offer_strategy.py`.

### Technical demo / evergreen pre-nurture
Retain short technical screen demos as evidence-backed sales assets. Demos
should show real capabilities such as signal discovery, qualification, CRM,
conversion, buyer routing and follow-up. Historical claims such as fixed PPC
costs, job values or ROI ranges are not allowed unless current verified
evidence supports them.

### Engagement rescoring
Retain telemetry-driven rescoring, but only from observed engagement events.
Clicks, completed lead magnets, pricing views and genuine replies can alter a
bounded engagement score. Bounce or unsubscribe hard-stops re-engagement.

### Parallel specialist model
Retain specialist agents, but use current Swarm V6:
- Revenue / Payments
- Closer / Outreach
- Growth / Conversion
- Search / Opportunity
- Platform / SaaS
- Integration / QA

Astra is the commander. Swarm V6 does not become a second authority plane.

## Adapt later when economically justified

### LangGraph
Useful only if the native state machines become materially harder to maintain
or need checkpointed graph execution that existing Supabase workflows cannot
provide. It is not required for launch.

### Redis event bus
Not required today. Current Supabase/runtime orchestration is sufficient.
Introduce Redis only when measured throughput or latency requires it.

### PostHog
Potentially useful as a first-party web/product telemetry adapter. Conversion
Intelligence can accept PostHog evidence later, but PostHog is not canonical
commercial truth.

### Lago / OpenMeter
Potential usage-metering adapters. Empire already has native evidence-first
commercial usage metering. Add an external metering engine only when SaaS
volume justifies it.

### Authentik / Keycloak
Potential enterprise SSO providers after tenant/customer demand justifies the
operational burden.

### AI video studio + browser recording
The target is a hybrid AI video studio rather than a plain recorder: real Empire browser/data captures remain the proof layer, while optional AI video generation can add motion, transitions, narration, visual b-roll and social cuts. The governed layers now exist at `empire_os/video_demo_plan.py` and `empire_os/video_studio_v1.py`. Playwright/FFmpeg and a video-generation model remain adapters to activate deliberately when the production renderer is built. Viewer completion/CTA telemetry will feed Conversion Intelligence.

### Incus / bare-metal expansion
Keep Incus and additional Vultr/Hetzner nodes as scale options. Do not migrate
working production infrastructure merely to match a historical diagram.

## Retired / prohibited from canonical architecture

- Solana/USDC settlement. Canonical payment rail is USDT on BSC.
- Direct self-serve payment or settlement that bypasses governed payment truth.
- Rotating proxies or techniques intended to bypass firewalls/access controls.
- Synthetic or fabricated lead, pricing, conversion, revenue or benchmark data.
- Historical fixed market claims such as PPC costs, appointment costs, job
  values or setup pricing as production truth.
- A hard-coded Omega threshold of 90 for every niche. Thresholds are
  evidence-backed and niche-configurable; current default planning threshold is
  70 unless policy/evidence says otherwise.
- "Zero human intervention" as an authority doctrine. Reversible internal work
  can automate; binding terms, funds, accounting truth and authority expansion
  remain governed.
- The legacy public/file-backed Swarm 3.0 bus.
- Legacy synthetic funnel/SQLite commercial state.
- "Subconscious" or manipulative outreach language. Canonical outreach is
  concise, truthful, relevant, opt-out compliant and evidence-backed.

## Canonical flow after salvage

REAL SIGNAL
→ NICHE CONFIG / ICP
→ KEYWORD + INTENT EVIDENCE
→ OMEGA / QUALIFICATION
→ MICRO LEAD MAGNET / DEMO PLAN
→ FIRST-PARTY BUYER DISCOVERY
→ GOVERNED OUTBOUND
→ ENGAGEMENT TELEMETRY / RESCORE
→ CLOSER
→ CAPACITY
→ VERIFIED COMMERCIAL EVIDENCE
→ TERMS
→ BSC USDT
→ FULFILMENT
→ REVENUE TRUTH / GP
→ CONVERSION INTELLIGENCE
→ ASTRA / SWARM V6 LEARNING

## Immediate implementation status

- Swarm V6: active, timer-backed.
- Multi-niche GTM planning: local/tested.
- Micro lead-magnet routing: local/tested.
- Engagement rescoring: local/tested.
- Niche-tier / demo-asset planning: local/tested.
- Conversion Intelligence: live canonical snapshot.
- Revenue Exchange schema: activated in canonical Supabase.
- Commercial evidence registry: activated in canonical Supabase.
- LangGraph / Redis / PostHog / Playwright: intentionally not installed.

## Video / YouTube / Social Automation — deferred rebuild

Historical EmpireOS code confirms the earlier stack included OpenMontage/OpenCut-oriented video editing plus YouTube/social syndication concepts. Those paths are now legacy references, not canonical runtime.

The rebuild target after first-revenue proof is:

REAL EMPIRE WORKFLOW → PRIVATE SYSTEM RECORDING → EDIT/COMPOSITE → LONG-FORM DEMO → SHORTS/SOCIAL CUTS → GOVERNED PUBLISH QUEUE → VIEW/CTA/REPLY TELEMETRY → CONVERSION INTELLIGENCE → ASTRA LEARNING.

Recovered design references include the legacy `video_editing_agent.py`, `social_syndication.py`, `social_youtube.py`, `youtube_uploader.py` history and the social-video clipify prompt. We will re-evaluate the open-source renderer/editor stack rather than restoring OpenMontage blindly.

Current canonical foundations are `empire_os/system_demo_recorder.py`, `empire_os/video_demo_plan.py` and `empire_os/video_studio_v1.py`. Browser/render/publishing adapters remain disabled until intentionally selected and configured.

### GPU rendering architecture

Video rendering/generation will run on a separate GPU worker rather than the core EmpireOS control-plane host. EmpireOS owns manifests, evidence, queueing, governance and telemetry; the GPU node owns browser capture/render/generation jobs and returns immutable artifacts/metadata. GPU failure must not block GTM, payments, CRM, Astra or Revenue Truth. Initial implementation should use a single worker with bounded concurrency and a provider-agnostic adapter so local/bare-metal or rented GPU capacity can be swapped later.
