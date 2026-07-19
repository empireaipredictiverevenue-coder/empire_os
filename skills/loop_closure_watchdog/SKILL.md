---
name: loop_closure_watchdog
description: Business-loop health watchdog for Empire OS revenue funnel. Watches if money flows (S1→S5), detects silent email-delivery stalls, and self-heals known rot points. Run on a 5-min systemd tick.
trigger:
  - "loop stalled / no applications / emails not sending"
  - "outbox backlog growing but nothing sent"
  - "systemd empire-agent-loop-closure.service tick"
  - scheduled: every 300s via empire-agent-loop-closure.service
---

# SKILL: loop_closure_watchdog

## What it does
Polls the live SQLite DB + unit states every 5 min and verifies the revenue loop
is progressing. Catches the class of failure where processes are UP but MONEY is
silent (e.g. 2026-07-19: hub /v1/outbox/pending SQL excluded recipient_kind='prospect'
→ 1250 real founder emails sat pending, 0 sent, 40+ min, nothing alerted).

## When to run
- Always running as a daemon (empire-agent-loop-closure.service). Do NOT invoke manually
  except for `--once` debugging.
- After any hub/email change, run `--once` to confirm no false stalls.

## Steps (per tick)
1. `self_heal()` — re-pin dead Hermes models, restart dead empire units,
   and if outbox stalled: force EMAIL_BACKEND=brevo + restart mail-sender.
2. `stage_freshness()` — count + age of each loop stage from DB.
3. `outbox_flush_health()` — pending vs sent-in-window; flag stall.
4. `evaluate(st)` — alert on S1→S2, S2→S3, S4, global stalls.
5. Log + print; alert Telegram on any failure.

## Verification
- `incus exec empire-hub -- python3 -m empire_os.agents.loop_closure_watchdog --once`
  → should print stages + outbox, no traceback.
- Check /root/feedback/loop_closure.jsonl for OK/ALERT/FIX lines.

## Pitfalls
- The hub's /v1/outbox/pending SQL MUST include recipient_kind='prospect'
  (founder outreach uses that kind). If someone edits hub.py and drops it,
  emails silently stop — this watchdog's outbox guard will catch + heal, but
  the root fix is the hub SQL (see hub.py ~line 3085).
- EMAIL_BACKEND=direct hangs on cloud port-25 blocks (30s/email). Always brevo.
- DB is in the CONTAINER (/root/empire_os/empire_os.db), not host. Queries run
  inside empire-hub.
- Hermes state.db is on HOST (/root/.hermes/state.db) — re-pin there, not container.
