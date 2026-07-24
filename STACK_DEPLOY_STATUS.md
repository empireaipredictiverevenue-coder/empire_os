# Empire OS v3 Stack Deploy Status — Saved 2026-07-24 (Updated)

## LXC Fleet Ground Truth (from `incus list`)

| Container | Status | IP |
|-----------|--------|----|
| appsmith-admin | RUNNING | 10.118.155.154 |
| documenso | RUNNING | 10.118.155.30 |
| empire-hub | RUNNING | 10.118.155.218 |
| formbricks-survey | RUNNING | 10.118.155.88 |
| lead-sniper-agent | RUNNING | 10.118.155.68 |
| listmonk-mail | RUNNING | 10.118.155.153 |
| post-analytics | RUNNING | 10.118.155.13 |
| strix-sandbox | STOPPED | — |
| twenty-crm | RUNNING | 10.118.155.248 |

## HTTP Health Probes (from host, 2026-07-24)

| Service | Port | IP | HTTP Code | Status |
|---------|------|-----|-----------|--------|
| empire-hub | 8081 | 10.118.155.218 | 404 | ✅ Hub up (404 on `/` = healthy, `/health` = 200) |
| twenty-crm | 3000 | 10.118.155.248 | 404 | ✅ Up (404 on root = NestJS running) |
| documenso | 3500 | 10.118.155.30 | 302 | ✅ Up (redirect to login) |
| formbricks | 3000 | 10.118.155.88 | **200** | ✅ **Fixed** — was 000, now responding |
| listmonk | 9000 | 10.118.155.153 | 200 | ✅ Up |
| appsmith | 8080 | 10.118.155.154 | 200 | ✅ Up |
| posthog | 8000 | 10.118.155.13 | **301** | ✅ **Fixed** — was 000, now Django 301 redirect |

## Deep Health (from empire-hub container)

```json
{
  "ok": true,
  "revenue_path_ready": true,
  "checks": {
    "env": { "SOLANA_VAULT_WALLET": true, "SOLANA_RPC_URL": true, "SOLANA_PAYER_SECRET": true, "USDC_MINT": true, "SOLANA_NETWORK": true },
    "db": { "si_charges": true, "si_unmatched_deposits": true, "si_tenant": true, "si_settlements": true, "si_invoice": true, "writable": true },
    "chain": { "rpc": { "ok": true, "vault_balance_usdc": 0.521861, "token_accounts": 1 } },
    "hub": { "/health": { "ok": true }, "/v1/buyers/apply": { "ok": true }, "/v1/ppc/charge": { "ok": true } },
    "listener": { "process_count": 1, "pids": ["291"], "last_log_age_seconds": 23, "log_alive": true }
  }
}
```

## Core Services (Host PIDs)

| Service | PID | Description |
|---------|-----|-------------|
| Hub API | 2369286 | Main API on :8081 |
| Orchestrator | 1391835 | Agent coordination (systemd) |
| Mesh Agent | 1391840 | Inter-agent messaging |
| Lead Sniper | 2356935 | In-container (incus exec) |
| Solana Listener | 956 | USDC settlement monitoring |
| PP Router | 2338859 | PPC buyer marketplace |
| Mail Sender | 2350220 | Outbound email |
| Founder Outreach | 2109546 | Founder campaigns |
| North Mini | 1475 | Minimax customer intel |
| CEO Agent | 941 | OKF vision |
| Chief of Staff | 944 | Orchestrator |
| Deep Research | 945 | A2A/AEO research |
| PPL Service | 1445 | Pay-per-lead billing |
| Code Review | 1463 | QA agent |

## Cortex Swarm (inside empire-hub)

- Location: `/root/agentic_revenue/swarm.py`
- Components: Bridge + Scanner + Judge + Architect
- PID: 2371385 (host view)

## Crawler

- Command: `empire_os.crawler_runner --metro NYC --source permits`
- PID: 2361907
- Options: `--metro NYC|LA|CHI|HOU|PHX`, `--source permits|yelp|angie|bbb|google_maps`

## Action Items

- [ ] **twenty-crm** returns 404 on `/` — verify `/api/health` or `/health` endpoint
- [ ] Leads DB schema migration needed: missing `c.id` column on `/v1/leads`
- [x] Crawler stats endpoint `/v1/crawler/stats` **IMPLEMENTED** — returns 200 with daily lead volume, tier/strategy breakdown, expected revenue, top 5 latest

## Startup Script Location

`/root/empire_os/start_empire_os.sh` (from startup-procedure-2026-07-24.md)