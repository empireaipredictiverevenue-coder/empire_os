# EMPIRE OS AGENT GUARDRAILS
## Universal Rules for All Agents

### 1. DATA INTEGRITY
- **Never trust cached state** — Always read live DB/hub endpoints
- **Schema-aware queries** — Check `PRAGMA table_info` before SELECT/INSERT
- **Idempotent writes** — Use `INSERT OR REPLACE`, `UPDATE ... WHERE`, check existing before create
- **WAL mode** — All SQLite connections: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000;`

### 2. LLM USAGE
- **Priority order**: GOOGLE_API_KEY (Gemini) → GROQ_API_KEY → MINIMAX_API_KEY → OPENROUTER_API_KEY
- **Fallback chain**: Auto-select in `agent_core.py` — never hardcode provider
- **Graceful degradation**: If no keys, `_NoopLLM` returns structured empty; agent continues rule-based
- **Temperature**: 0.3 for decisions, 0.6 for content, 0.5 for reflection
- **Max tokens**: 800 for drafts, 2000 for analysis

### 3. RATE LIMITS & DEDUPE
- **Cortex AEO**: max 10 pages/run, skip if niche already published
- **Innovator**: max 3 proposals/cycle, dedupe by name+category
- **Business/CEO**: hourly, log only (no external API calls)
- **R&D**: max 5 opportunities/week, dedupe by signal source+topic

### 4. ERROR HANDLING
- **Consecutive failure backoff**: 60s * failures, max 600s (10min)
- **DB locked**: exponential backoff 0.5s, 1s, 2s, 4s, 8s (max 15s total)
- **Hub unreachable**: retry 3x, then log ERROR, continue rule-based
- **LLM failure**: structured_chat returns {} → agent uses rule-based fallback

### 5. LOGGING & OBSERVABILITY
- **All agents** write to `/root/feedback/<agent>_<date>.jsonl` (one JSONL line per event)
- **Cycle summary** to stdout: `{"cycle": "...", "summary": "..."}`
- **Errors** include: agent, cycle, error[:200], context
- **Metrics** emitted: decisions, proposals, pages, revenue_impact

### 5. SERVICE DEPLOYMENT
- **Systemd units**: `empire-<agent>.service` (Type=oneshot for timers)
- **Timers**: `empire-<agent>.timer` with appropriate cadence
- **Health endpoint**: Each agent exposes `/health` on unique port
- **WorkingDirectory**: `/root/empire_os`
- **Environment**: Load from `/root/empire_secrets/` + systemd drop-in

### 6. FEEDBACK PATH
- **Primary**: `/root/empire_os/feedback/` (writable, owned by root)
- **Avoid**: `/root/feedback/` (often owned by nobody in container)
- **Archive**: Weekly tarball of feedback/ to `/root/empire_os/archive/`

### 7. REVENUE LOOP GUARDRAILS
- **Never create fake leads** — Only real scraped/enriched data
- **Never mark paid without USDC confirmation** — BSC USDT listener + memo match
- **Settlement bridge** is the only path: invoice → paid → settlement → payout
- **Cortex guard** runs every 15min: hub health, processes, DB, stuck leads, stale invoices, mail

### 8. CONTAINER SYNC
- **Host edits don't reach container** — After any file change: `incus file push <host> empire-hub<container>` then `systemctl restart <service>`
- **Secrets**: `/root/empire_secrets/<name>` mode 600, fallback after env miss
- **Cloudflare blocked** — Route outbound email via hub `/v1/outbox/enqueue` (Brevo)

---

## AGENT-SPECIFIC GUARDRAILS

### Cortex Engine
- Max 10 AEO pages/run
- Dedupe: skip published niches
- Schema-aware: tolerates missing columns
- _NoopLLM if no keys

### CEO Agent
- Read-only on funnel
- Priority: replied(1) > matched(2) > funnel(3)
- Idempotent brief generation

### Business Agent
- Execute CoS tasks first
- LLM structured JSON output
- Log to `/root/business/decisions.jsonl`

### Innovator
- Max 3 proposals/cycle
- Ship action mandatory
- Score >= 3.5 = ship

### R&D
- Max 5 opportunities/week
- Free sources only
- Build vs Buy decision required

### All Agents
- No external paid APIs without keys in `/root/empire_secrets/`
- No writes to funnel/prospect tables (except designated owners)
- Consecutive failure backoff
- Health endpoint required