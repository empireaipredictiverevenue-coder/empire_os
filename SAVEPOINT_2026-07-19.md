# EMPIRE OS — AGENT SAVEPOINT (2026-07-19)

> **Purpose:** Any future agent (different model/brand) reads THIS to resume with full context.
> **How to access:** Say "read /root/empire_os/SAVEPOINT_2026-07-19.md and g-brain/system/state.md and continue."
> **Source of truth:** `/root/g-brain/system/state.md` (updated by north-mini) + this savepoint + live session DB.

---

## 1. WHO/WHAT EMPIRE OS IS
- Founder-run lead-gen + predictive-revenue infra. Empire OS v3. Domain empire-ai.co.uk.
- Business = "Predictive Revenue" / Autonomous Ad-Intelligence Infrastructure (NOT a marketing agency).
- "The Empire Cortex" = the Decentralized Agent Swarm (Scanner + Judge + Architect + Bridge) — see §4.
- Real money = USDC crypto payouts (Solana). PayPal email offcicialphilliplivesley@gmail.com is identifier ONLY — never paste private keys, public wallet addr only.

## 2. DEPLOY INFRA
- Host: Linux Vultr VPS 216.128.149.56. Incus/LXC containers. Coolify optional.
- Main container: `empire-hub` (IP 10.118.155.218, hub port 8081). Code at `/root/empire_os/` on host = SAME tree as `/root/empire_os/` in container (sync via `incus file push/pull`).
- Host FS and container FS are SEPARATE. Edits in container need `incus exec empire-hub -- ...` or `incus file push`.
- Cloudflare Tunnel (host systemd `cloudflared-empire.service`) → AEO pages live at empire-ai.co.uk (200). www CNAME not set (404, non-blocking).
- Cron/daemons = systemd (Restart=always) preferred over one-off scripts.

## 3. WHAT WE BUILT + VERIFIED THIS SESSION (real, running)
| Component | Path | Status |
|---|---|---|
| cortex_engine.py (4-pillar predictive revenue intel + recurrence guard) | /root/empire_os/empire_os/agents/cortex_engine.py | LIVE, systemd timer every 15 min (container) |
| recovery_sequence.py (3-touch USDC recovery on $298k uncollected) | /root/empire_os/empire_os/agents/recovery_sequence.py | LIVE, daily 09:00 timer |
| qc_agent.py (12/12 health probe) | /root/empire_os/empire_os/agents/qc_agent.py | LIVE, host timer every 15 min |
| loop_closure_watchdog.py (outbox flush + self-heal) | /root/empire_os/empire_os/agents/loop_closure_watchdog.py | LIVE, every 5 min |
| agent_core.py OllamaClient→OpenRouter fallback | /root/empire_os/empire_os/agent_core.py | FIXED (dead Ollama host → openai/gpt-4o-mini) |
| innovator_agent / growth_agent (CRM-driven) | /root/empire_os/empire_os/agents/*.py | FIXED, read live CRM |
| crm_setup.py / crm_cli.py (697 contacts, 498 deals $298,901) | /root/empire_os/empire_os/agents/*.py | WORKING |
| AEO pages (279 with CTAs) + sitemap + GSC submitted | /srv/aeo (container) + hub | LIVE, GSC status 0 |
| payout engine (Solana USDC transfer) | /root/empire_os/empire_os/payout.py + payout_batch.py | CODE READY, NOT TRIGGERED (no hourly scheduler yet) |

## 4. THE EMPIRE CORTEX SWARM (pre-pivot vision — REBUILD TARGET)
Location: `/apis/agentic_revenue/` (host). 4 agents:
- **Scanner** (The Eyes): polls ScrapeCreators for ad transcripts/thumbnails → extracts raw patterns. FILE `scanner/main.py` = STUB (19 lines, Placeholder class). NEEDS REAL IMPL.
- **Judge** (The Brain): LangGraph + Gemini, grades against Empire Quality Rubric (Stopping Power / Hook Strength / Conversion Intent) using synthetic personas. FILE `judge/main.py` = 376 lines REAL but needs `langgraph` + `google.genai` (NOT installed → crashes on import).
- **Architect** (The Creator): takes "Gold Standard" blueprints (Supabase pgvector) → synthesizes "Exact Copy" assets for niche (Roofing/Mass Tort). FILE `architect/main.py` = 512 lines REAL but needs `supabase` (has MockSupabaseClient fallback).
- **Bridge**: inter-agent message queues. FILE `bridge/inter_agent_bridge.py` = 210 lines REAL, self-contained (no external deps).

**The French "hourly payment to wallet" you remembered:** It was a FABRICATED pitch in session `20260718_120153_04d254` (French assistant output, NOT a file). Claimed "JUGE D'ÉVALUATION = $121+/heure → YOUR WALLET". That was fiction (0 real revenue). The REAL cortex is the 4-pillar engine we built (§3), not the $87k/month fiction. DO NOT rebuild the fiction — rebuild the actual swarm (§4) and wire it to real payouts.

## 5. THE "HERMES PROMPT" (from original cortex spec — use to re-align any agent)
"Act as Lead Systems Architect for Empire AI. Build autonomous agentic ad-generation infrastructure in Incus containers. Agent Isolation: scanner/judge/architect each in own container. Communication: internal bridge network + Supabase pgvector shared truth. Reasoning: LangGraph agentic patterns, Judge critiques Architect before dashboard approval. Data: 'Exact Copy' methodology — scraped ads → Visual DNA + Script DNA blueprints → Architect builds your version."

## 6. OUTSTANDING WORK (build it all, return to pre-pivot)
1. **Revive Cortex swarm:** install `langgraph` + `google-generativeai` (or refactor judge to use OpenRouter already configured) + `supabase`; fix scanner stub; run bridge+3 agents.
2. **Hourly payout scheduler:** build `payout_scheduler.py` (systemd timer, hourly) → pays settled invoices to wallet via `payout.usdc_transfer`. Needs SOLANA_PAYER_SECRET + funded vault (NOT yet set).
3. **Wire cortex_engine → north-mini:** already mirrored cortex_snapshot.json; confirm north-mini reads it.
4. **Scale:** scrape 735→10k+ prospects; nightly CRM backfill cron.
5. **First real USDC payment** closes the loop (S4/S5 currently 0).

## 7. KEY SECRETS / PATHS (REDACTED — use env, never hardcode)
- OpenRouter: /root/.empire_secrets/openrouter.env + container .env OPENROUTER_API_KEY
- Telegram notify: /root/.empire_secrets/telegram.env (CHAT_ID 808657420, MONEY_ONLY=1)
- GSC: /root/.gsc-creds.json (service acct empire-ai@empire-ai-494717)
- Cloudflare tunnel token: in cloudflared config (host)
- SOLANA_VAULT_WALLET: container .env (public addr). PAYER_SECRET: NOT SET — required for payouts.
- Brevo/Hunter/MiniMax keys: container .env

## 8. VERIFICATION HABIT (mandatory before "done")
After code edits, write `/tmp/hermes-verify-*.py`, run INSIDE container (`incus exec empire-hub -- /root/venv/bin/python3 ...`), clean up. Report as AD-HOC, not suite green.
