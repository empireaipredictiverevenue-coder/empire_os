# EmpireOS Swarm V6 Operating Spec

## Purpose

Swarm V6 is the governed parallel specialist layer beneath Astra. It replaces the retired public/file-backed Swarm 3.0 execution model.

Astra remains the commander/orchestrator. Swarm V6 continuously assigns bounded deterministic verification work to specialist Coder lanes.

## Canonical lanes

1. Revenue / Payments
2. Closer / Outreach
3. Growth / Conversion
4. Search / Opportunity
5. Platform / SaaS
6. Integration / QA

Each lane owns a small declared set of modules and focused tests. Lanes do not write production business state.

## Authority

Swarm V6 mode is INTERNAL_VERIFY.

It has no authority to mutate production business data, send outreach, approve or accept commercial terms, move funds, confirm payments, fulfil buyer work, recognize revenue, expand its own authority, deploy, or mutate infrastructure.

Those actions remain with their canonical governed workers and human/standing authority gates.

## Runtime

- Core: empire_os/swarm_v6.py
- Runner: scripts/run_swarm_v6.py
- Snapshot: runtime/swarm_v6/latest.json
- Service: empire-swarm-v6.service
- Timer: empire-swarm-v6.timer
- Default cadence: every 30 minutes
- Parallel workers: 3
- Work type: Empire Coder VERIFY

The queue is replenished only when there is no pending/running Coder work, so Swarm V6 does not duplicate active jobs.

## Relationship to other systems

- Astra: commander and company operating layer.
- Empire Coder: repository-aware task/verification worker used by the lanes.
- Hermes: optional planning/implementation intelligence; not required for deterministic VERIFY cycles.
- Conversion Intelligence: Growth/Conversion specialist capability.
- GTM / Closer / Payments / Revenue Truth: canonical execution systems, outside Swarm V6 authority.

## Legacy Swarm 3.0

The following are historical and must not be reactivated as production execution paths:

- public /v1/swarm/worker-config mutation;
- unauthenticated /v1/swarms/events file-backed event writes;
- /root/swarms/*.jsonl as canonical state;
- legacy swarm prompt/ledger endpoints;
- synthetic-agent production fallback.

Historical SOUL files may be used as design evidence only when reconciled with Blueprint v6 and current governance.

## Multi-Niche GTM extension

The Closer / Outreach lane also verifies the native multi-niche GTM extension:

- `empire_os/gtm_swarm_v6.py` — niche/ICP/metro configuration, score thresholding, micro lead-magnet routing, engagement rescoring and governed outbound handoff.
- `empire_os/gtm_offer_strategy.py` — niche-tier review, evidence-first technical demo/pre-nurture assets and high-ticket offer framing.
- `empire_os/video_demo_plan.py` — governed evidence-backed screen-demo manifests.
- `empire_os/video_studio_v1.py` — hybrid AI video-studio planning: real product/data captures as the proof layer plus optional generated motion/b-roll, narration, captions, chapters, CTA, social cuts and viewer telemetry. Generated media never becomes commercial evidence.

This extension does not introduce a second send engine. All execution still passes through the canonical GTM/outbound governor. LangGraph/Redis/PostHog can be added later as adapters only when measured need justifies them.
