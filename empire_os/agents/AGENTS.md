# Empire OS v3 — Agent Fleet

Each agent runs in its own Incus container with its own identity (SOUL.md),
its own log, and its own observe-reason-act cycle. **No cron, no schedules**
— each agent decides when to tick internally. A single orchestrator
(`/root/empire_os/scripts/orchestrator.py`, running as systemd
`empire-orchestrator.service`) keeps them alive.

## Active Agents

| Agent | Container | Role | Tick | Purpose |
|---|---|---|---|---|
| **Mesh** | mesh-agent | coordinator | 60s | Fleet health + cross-agent routing |
| **Business** | business-agent | strategist | 1h | Daily decision surface |
| **Growth** | growth-agent | hunter | 30m | Opportunity + gap finder |
| **Engineering** | engineering-agent | mechanic | 10m | Broken-stuff ticket queue |
| **Scheduling** | scheduling-agent | closer | 5m | Book claimed leads |
| **Copywriting** | copywriting-agent | voice | 15m | Landing page + ad copy |
| **Email** | email-agent | pen | 10m | Outreach email drafts (queue only) |
| **Predictive** | predictive-agent | forecaster | 24h | Revenue + gap/leak/waste |

## Legacy Agents (built earlier)

| Agent | Container | Role |
|---|---|---|
| empire-hub | empire-hub | Core hub + funnel + CRM |
| agi-scout | agi-scout | AGI market intelligence |
| agi-marketing | agi-marketing | AGI content gen |
| seo-agent | seo-agent | Traditional SEO audit |
| ai-seo-agent | ai-seo-agent | AI content quality + programmatic SEO |
| lead-filter | lead-filter | Lead qualification |
| storm-agent | storm-agent | Weather signals |
| reddit-sniper | reddit-sniper | Social lead capture |
| satellite-agent | satellite-agent | Geo imagery |

## Predictive Revenue + Gap Detection

The **Predictive Agent** runs `/root/empire_os/empire_os/predictive.py`
daily and produces four outputs:

1. **Revenue projection** — formula:
   ```
   active_seats_mrr = occupied_lanes × avg_seat_price
   projected_new_mrr = leads × conversion × seat_price × funnel_velocity
   total_predicted_mrr = active_seats_mrr + projected_new_mrr
   unrealized_mrr = empty_lanes × avg_seat_price
   confidence = log10(sample_size) / 3
   ```
2. **Market gaps** — hot (raise price), unsaturated (recruit), dead (kill/pivot)
3. **Leaks** — funnel drop-offs between states, with inferred cause
4. **Waste** — over-resourced lanes, idle agents, error hotspots

Latest snapshot: `/root/feedback/predictive_YYYYMMDD_HHMMSS.json`

## Shared Infrastructure

- **Registry**: `/root/empire_os/config/agent_registry.json`
- **Orchestrator**: `systemctl status empire-orchestrator`
- **Feedback engine**: `/root/empire_os/scripts/feedback_engine.py`
- **Agent bootstrap**: `/root/empire_os/scripts/agent_registry.py`
- **Synthetic base**: `/root/empire_os/empire_os/synthetic_agents.py`
- **Predictive formulas**: `/root/empire_os/empire_os/predictive.py`
- **Souls**: `/root/empire_os/empire_os/agents/souls/`

## Agent Lifecycle

1. **Provision**: `agent_registry.py create <name> <role> --port <p>`
2. **Soul written**: `souls/<role>_SOUL.md` defines identity + principles
3. **Code deployed**: `agents/<role>_agent.py` extends `SyntheticAgent`
4. **Log path**: `/root/<role>/<role>.log`
5. **Health URL**: `http://localhost:<port>/health`
6. **Discovered by**: orchestrator reads registry, spawns loop, monitors liveness

Every new agent follows this pattern. The registry + orchestrator + synthetic
base + predictive engine make adding a new agent a 4-step operation:
write the soul, write the agent, provision the container, register it.
