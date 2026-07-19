# Loop Closure Watchdog — Skill Spec

Used by `loop_closure_watchdog.py` each 5-min tick. Goal: detect money-loop
stalls and self-heal the 3 known rot points. This is the operational contract.

## Stages checked (evaluate())

- **S1→S2 STALLED**: s1_emails_sent>0 AND s2_subs_total==0.
  Cause: email has no pay_url OR /v1/buyers/apply down.
- **S2→S3 STALLED**: s2_subs_awaiting>0 AND s3_awaiting_with_ref==0.
  Cause: crypto_payment_request failed or _deliver_pay_link broken.
- **S4 STALLED**: s2_subs_active>0 AND s4_charges_total==0.
  Cause: lead_deliverer not billing per-lead.
- **GLOBAL STALL**: max stage age > STALE_MIN (180). Loop went silent.
- **OUTBOX STALLED**: outbox_pending>20 AND outbox_sent_recent==0.
  Cause: mail-sender wedged / EMAIL_BACKEND=direct (port-25 hang) /
  hub /v1/outbox/pending not returning prospect rows.

## Self-heal actions (self_heal())

1. **Dead model re-pin** — state.db sessions with model NOT IN
   ('tencent/hy3:free') → UPDATE to hy3. (HOST-only: state.db lives on host.)
2. **Dead unit restart** — for each empire-* unit, if `systemctl is-active`
   != active → `systemctl restart`. Correct unit names use UNDERSCORES
   (empire-agent-solana_listener.service, NOT empire-agent-solana-listener).
3. **Outbox guard** — if outbox_stalled: call _ensure_brevo_backend()
   (rewrites EMAIL_BACKEND=direct → brevo in /root/empire_os/.env) then
   `systemctl restart empire-mail-sender.service`.

## Verification (how to confirm it works)

```bash
incus exec empire-hub -- python3 -m empire_os.agents.loop_closure_watchdog --once
# expect: no ALERT lines, outbox: {"outbox_stalled": false, ...}
journalctl -u empire-agent-loop-closure.service --no-pager -n 3
# expect: "loop start" + periodic "stages:" lines
```

## Pitfalls (do NOT repeat)

- **recipient_kind='prospect' excluded from /v1/outbox/pending** — the hub
  query only returned NULL/'buyer'/'owner'(consented). Founder emails use
  'prospect' → silently never sent. FIXED in hub.py (added OR recipient_kind='prospect').
- **EMAIL_BACKEND=direct on cloud** — raw MX send hangs ~30s on blocked
  port 25 → ~2 emails/min throughput + false "sent". Always brevo.
- **Wrong unit name (hyphen vs underscore)** — restart targets the wrong unit,
  silently no-ops. Use the underscore form.
- **Stale host DB mirror** — /root/empire_os/empire_os.db on HOST is NOT the
  live DB (lives in container). Any check reading the host copy sees stale data.
- **Hub restart wedges mail-sender** — during a hub restart, mail-sender's
  _hub_get catches Connection refused and returns None; loop must retry next
  tick, not die. Confirm daemon resumes after hub comes back.
