# Empire Ambient AI — Positioning & Pitch

## What it is
Empire Ambient AI is our **always-on, self-hosted autonomous revenue layer**. A fleet of
agents that run continuously in the background, monitor live market signals, simulate
before they act, execute, and self-heal — without a human prompting each step.

Competitors (Salesforce Agentforce, Glean) rent you autonomous agents per seat at SaaS
prices. We run the same class of agent **on our own metal** — no per-seat tax, no
rented infra, no data leaving our stack.

## The 23-layer brain (predictive_cloud.py)
- Layers 1–21: world-model routing, utility-suite gen, market sweep, omni-agent status.
- Layer 22 / 22b: Hermes v9 growth engine + REAL signal feed (Reddit, inbound replies,
  buyer-intent lanes, GEO/AEO audits) → Customer-Truth / Objection / Growth maps.
- Layer 23: AGI Synthetic Intelligence — simulation-first campaign validation +
  telemetry-driven auto-patching (self-healing swarm).

## How the ambient loops earn (today, live)
1. **Market sweep** (cron 15m) — rotates all 115 niches, Serper multi-intent sweep →
   self-hosted Waterfall enrich → A2A buyer marketplace. Zero external API rent.
2. **Hermes signal feed** (cron 20m) — real buyer/HOT_BUYER signals → auto_onboard
   pay-link (zero-friction, no call).
3. **AGI sim** (cron 30m) — validates offers against synthetic personas built from real
   crm_leads; auto-patches breaching agents (restarts omni-agent on latency/margin breach).
4. **Ambient watchdog** (cron 15m) — single health surface; restarts dead loops.

## Pitch (use in outbound / AEO pages)
> "Your competitors rent Salesforce Agentforce and pray the seat price pays off. Empire
> Ambient AI runs autonomous revenue agents on your own infrastructure — always-on,
> self-healing, zero SaaS tax. It finds the buyers, qualifies them, and closes the loop
> while you sleep. No per-seat rent. No phone call. Just revenue."

## Upgrade path (make Layer 23 revenue-direct)
- Feed live conversion telemetry (per-event margin, latency) into swarm_telemetry so
  auto-patching triggers on REAL breaches, not simulated.
- Route passed simulations (confidence >= 0.80) into the actual deployment bus → live
  campaign launch, pre-validated.
- White-label: per-client container = the per-niche ambient agent (product for enterprise
  tier, not needed for our own gen).

## Status
- Brain: 23 layers. Containers: omni-agent (host :3997 + container), Twenty CRM (:3000),
  Listmonk (:9000, admin auth pending). All crons autonomous, local-only.
- Real infra: pgvector (synthetic_personas, simulation_runs, discovered_niches,
  swarm_telemetry, auto_patches), Brevo relay, self-hosted Serper.
