# EMPIRE OS — FULL RECOVERY RUNBOOK (CORRECTED 2026-08-29)

Read FIRST after any crash / terminal loss / fresh session.

## 0. IMPORTANT — PREVIOUS DOC WAS WRONG
The 2026-08-29 "KEY LIVE NUMBERS" block was FABRICATED/inflated:
  doc claimed lane_leads 205,011 / buyer_leads 55,274 / cortex_blueprints 1,054 / DB 208MB
  REALITY: lane_leads 4,666 / buyer_leads 50 / cortex_blueprints 0 / DB 16MB
Do NOT trust recovery-doc counts. Always re-measure with the section-1 commands.

## 1. 60-SECOND HEALTH CHECK (run after any reconnect)
IMPORTANT: hub API lives INSIDE the empire-hub container. Curling 127.0.0.1:8081
from the HOST returns HTTP=000 (connection refused). Run checks via:
  incus exec empire-hub -- curl -s http://127.0.0.1:8081/health
And to verify the model-session drop was NOT your infra:
  incus exec empire-hub -- journalctl -u empire-hub-8081 --no-pager -n 5 | grep -E "200 OK|GET"
If you see "200 OK" lines, YOUR SERVERS ARE UP — the timeout was the Hermes<->model link,
NOT Empire OS. Do not "fix" things that are already running.

```bash
incus list                                          # empire-hub must be RUNNING
incus exec empire-hub -- systemctl is-active empire-hub-8081 empire-bsc-listener empire-lanes empire-mail-sender
incus exec empire-hub -- curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8081/health
incus exec empire-hub -- sqlite3 /root/empire_os/empire_os.db "PRAGMA integrity_check;"
incus exec empire-hub -- df -h / | tail -1          # MUST stay <90% or watchdog fails
```

## 2. CRASH RECOVERY (host rebooted / incus gone)
```bash
incus start empire-hub empire-revenue empire-storm lead-sniper-agent listmonk-mail
incus exec empire-hub -- systemctl restart empire-hub-8081 empire-bsc-listener empire-lanes empire-mail-sender empire-mcp empire-neural-scout empire-satellite-service empire-storm-predictor empire-a2a-buyer-marketplace
```

## 3. CODE RECOVERY
```bash
cd /root/empire_os && git pull            # host repo
git status                                # check for uncommitted hotfixes
```
Note: RECOVERY.md and *.db are gitignored (runtime data). Code fixes are committed.

## 4. DB RECOVERY
Backups live at /root/empire_os/backups/*.db (hourly, trimmed to <1 day).
If corruption: cp a recent backup over empire_os.db then integrity_check.

## 5. REAL KEY NUMBERS (measured 2026-08-29 12:40 UTC)
lane_leads=4,666 | buyer_leads=50 | delivered_leads=4,666 | si_outbox=2,061 (1 pending)
cortex_blueprints=0 | outbound_campaigns=12 | cortex_api_keys table EXISTS NOW (was missing, created this session)
BSC listener: ACTIVE, wallet 0x1339b487046B0ad924a10c20b1791608EA8595a8, balance readable.
Hub 8081: serving 200s (/health, /aeo/*, /v1/agents all OK).
Disk: 94% — watchdog failing at >90%, trim backups if it climbs.

## 6. PRODUCTS / SKUS (hub PRODUCT_PRICES)
- serp_sweep_100 $297, serp_sweep_250 $597, serp_lane_feeder $897 — delivery via bsc listener
- cortex_blueprint_pack $299 (T2 $747.50, T3 $1495, T4 $2990) — requires cortex_api_keys table (now created)
- Payment rail: BSC USDT listener, vault 0x1339...595a8. Paid SKU = auto-deliver end-to-end.

## 7. EMAIL RULES
Host IP Cloudflare-blocked on Resend (1010) -> EMAIL_BACKEND=brevo, key /root/empire_secrets/brevo_api_key.
Outbox table si_outbox. Mail sender runs INSIDE hub container.
nudge_awaiting needs /root/empire_os/.env + llm.env both loaded (BSC_WALLET_ADDRESS in llm.env).

## 8. DNS (fixed)
hub:/etc/systemd/resolved.conf.d/fallback.conf -> FallbackDNS 1.1.1.1 8.8.8.8 9.9.9.9.
services.spc.noaa.gov is NXDOMAIN GLOBALLY — storm predictor uses mapservices.weather.noaa.gov.

## 9. DISK HYGIENE (CRITICAL — was at 95%, watchdog failing)
Big non-Empire repos under /root (do NOT delete unless disk critical):
  EmpireHermes, astryx, browser-use, hyperframes, avatar_env, coldoutboundskills, agent_work, _inbox, feedback, mesh, code_review, g-brain, node_modules, hunt_venv
Empire OS itself: /root/empire_os (~2.1G). Backups trimmed to <24h.
Free space rule: keep root <90%. If >90%: rm old /root/empire_os/backups/*.db (older than 1 day), trim logs.

## 10. SESSION DROP PROTOCOL (so a lost model connection loses no work)
1. Long-running / multi-step work runs in tmux or background terminal (survives the drop).
2. Commit code fixes to git after EACH fix (don't batch).
3. Write a HANDOFF.md with: what was done, what's verified, next step.
4. On reconnect: read RECOVERY.md + HANDOFF.md, re-run section-1 health check, continue.
The drop is the model link, not your servers. Re-measure, don't rebuild.

## 11. VENDOR KEYS (needed to RUN, not customer data)
Brevo (email), Supabase (agent heartbeats), Pinecone (vectors), Serper (search).
These are OUR infra. cortex_api_keys is OUR product's buyer-auth table (keys we issue to buyers).
None are "someone else's keys for our product" — that framing was a misunderstanding.
