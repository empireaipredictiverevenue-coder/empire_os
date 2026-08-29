# EMPIRE OS — FULL RECOVERY RUNBOOK
Updated: 2026-08-29. Read this FIRST after any crash, terminal loss, or fresh session.

## 0. WHAT LIVES WHERE

| Layer | Location | Notes |
|---|---|---|
| Host VM | this Linux box, /root | incus runtime, git repo, secrets |
| Code | /root/empire_os (git repo, GitHub remote `origin master`) | source of truth for code |
| Secrets | /root/empire_secrets/<name> mode 600 | brevo_api_key, llm.env, etc. |
| Hub container | incus `empire-hub` 10.118.155.218 | runs EVERYTHING; /root/empire_os inside too |
| Other running containers | empire-revenue, empire-storm, lead-sniper-agent, listmonk-mail | STOPPED by design: twenty-crm, post-analytics, agent-doors, conversion-agent, copywriting-agent, graphify, senior-list-email-agent |
| Main DB | hub:/root/empire_os/empire_os.db (~208MB, WAL, ~99 tables) | hourly backup to hub:/root/empire_os/backups/ |
| Remote DB | Supabase (SUPABASE_URL in hub:/root/empire_os/.env) | agent_registry heartbeats + sync |
| Edge | Vultr 216.128.149.56 | public edge; skills empire-vultr-app-host, empire-os-edge-deploy |
| Brand/site | empire-ai.co.uk | AEO pages publish here |

## 1. 60-SECOND HEALTH CHECK (run after any reconnect)

```
incus list                                   # empire-hub must be RUNNING
incus exec empire-hub -- systemctl list-units --type=service --no-pager --no-legend | grep empire | grep -v running
incus exec empire-hub -- curl -s http://127.0.0.1:8081/v1/products | head -c 200
incus exec empire-hub -- systemctl is-active empire-bsc-listener empire-mail-sender empire-storm-predictor
incus exec empire-hub -- sqlite3 /root/empire_os/empire_os.db "PRAGMA integrity_check;" 
incus exec empire-hub -- ls -t /root/empire_os/backups/ | head -2   # backup age < 2h
```

Core services that must be active: empire-hub-8081, empire-bsc-listener, empire-lanes, empire-mail-sender, empire-mcp, empire-neural-scout, empire-satellite-service, empire-storm-predictor, empire-a2a-buyer-marketplace, empire-metrics-exporter, empire-last30days.
Timers: db-backup+wal-checkpoint (hourly), health-guard, disk-watchdog, intel-market, crawler-chicago, crawler-losangeles, serp-feeder (Mon), mrr-billing (Tue), cortex-engine, health-butler, health-deep.

## 2. CRASH RECOVERY (host rebooted / incus gone)

```
incus start empire-hub empire-revenue empire-storm lead-sniper-agent listmonk-mail
incus exec empire-hub -- systemctl restart empire-hub-8081 empire-bsc-listener empire-lanes empire-mail-sender empire-mcp empire-neural-scout empire-satellite-service empire-storm-predictor empire-a2a-buyer-marketplace
# then run section 1 health check
```
Container stopped = cost saving, per Philip (delete STOPPED only if disk >93%).

## 3. CODE RECOVERY (lost terminal / new session)

1. New Hermes session auto-loads memory + skills. Then: load skill `empire-session-reground`.
2. Code: cd /root/empire_os && git pull (host) — GitHub private repo, token in remote URL.
3. Latest commit at time of writing: cortex_blueprint_pack SKU, DNS fallback, recovery docs.
4. Uncommitted hotfixes: check `git status` on HOST and inside hub container (they drift — always diff both).

## 4. DB RECOVERY (corruption / bad migration)

```
incus exec empire-hub -- systemctl stop empire-hub-8081
incus exec empire-hub -- cp /root/empire_os/backups/<latest>.db /root/empire_os/empire_os.db
incus exec empire-hub -- sqlite3 /root/empire_os/empire_os.db "PRAGMA integrity_check;"
incus exec empire-hub -- systemctl start empire-hub-8081
```
Hourly backups (208MB each, ~4.3G retained). Supabase is system of record for agent heartbeats; SQLite is system of record for leads/revenue.

## 5. KEY LIVE NUMBERS (2026-08-29)
lane_leads 205,011 | buyer_leads 55,274 | delivered_leads 4,666 | si_outbox 5,582 | cortex_blueprints 1,054 | outbound_campaigns 5 | cortex_api_keys 0 (first buyer creates first key via /v1/cortex/signup).

## 6. PRODUCTS / SKUS (hub PRODUCT_PRICES)
- serp_sweep_100 $297, serp_sweep_250 $597, serp_lane_feeder $897 — delivery via bsc listener _deliver_sku CSV; weekly empire-serp-feeder.timer
- cortex_blueprint_pack $299 (T2 $747.50, T3 $1495, T4 $2990) — listener pulls _fetch_blueprint + _niche_heat from cortex_api, branded email delivery
- lane seats, evaluation product (8-agent), AEO pages, mass tort pipeline, homeowner pipeline, a2a marketplace (escrow + quotes)
- Payment rail: BSC USDT listener on real vault 0x1339b487046B0ad924a10c20b1791608EA8595a8. Paid SKU = auto-deliver end-to-end, zero manual steps.

## 7. EMAIL RULES
Host IP Cloudflare-blocked on Resend (1010) → EMAIL_BACKEND=brevo, key /root/empire_secrets/brevo_api_key. Outbox table si_outbox. Mail sender runs host-native: `systemctl restart empire-mail-sender` is INSIDE hub container. nudge_awaiting needs /root/empire_os/.env + llm.env both loaded (BSC_WALLET_ADDRESS in llm.env).

## 8. DNS (fixed 2026-08-29)
hub:/etc/systemd/resolved.conf.d/fallback.conf → FallbackDNS 1.1.1.1 8.8.8.8 9.9.9.9. services.spc.noaa.gov is NXDOMAIN GLOBALLY (dead host); storm predictor correctly uses mapservices.weather.noaa.gov. Do NOT chase services.spc again.

## 9. SELF-HOSTED STACK (mostly stopped — restart only when needed)
- post-analytics (PostHog clone) 10.118.155.13:8000 — STOPPED container
- twenty-crm 10.118.155.248:3000 — STOPPED container
- listmonk-mail 10.118.155.153:9000 — RUNNING
- formbricks 10.118.155.88, documenso 10.118.155.30, appsmith 10.118.155.154 — endpoints documented in agents/stack_wireup.py (6h sync), containers absent
- Wire-up: hub:/root/empire_os/empire_os/agents/stack_wireup.py syncs leads→CRM, send_email→posthog, conversions→listmonk, AEO→formbricks, docs→documenso, decisions→appsmith

## 10. VENDOR SERVICES
- Supabase: system of record, agent_registry heartbeats (e.g. storm_predictor_v49 ACTIVE)
- Pinecone: PINECONE_API_KEY in hub .env; hub.py /v1/pinecone/client route; empire_os/pinecone_client.py + pinecone_config.py (llama-text-embed-v2); agents pinecone_bootstrap.py, pinecone_mcp_client.py; tests test_pinecone_*.py
- Brevo (email), Serper (search via hub /v1/web/search), NOAA SPC MapServer (storm), Vapi (omega AI calls, separate business), GitHub (code)

## 11. DASHBOARDS (all built, hub:/root/empire_os/empire_os/)
dashboard.py, dashboard_v2.py (real-time v3), revenue_dashboard.py, cli_dashboard.py, mcp_dashboard.py, mcp_status_dashboard.py.

## 12. AGENT FLEET
hub:/root/empire_os/empire_os/agents/ — 173 files, souls in agents/souls/. Registry = Supabase agent_registry (NOT SQLite). Overseer: agents/supervisor.py + supervisor_daemon. Watchdogs: loop_closure_watchdog, cortex_health_watchdog, guardian_agent.
