# QC Agent — Skill Spec

Used by `qc_agent.py` (host-side, every 15 min via timer). Goal: prove the
Empire OS revenue stack is actually working end-to-end. Operational contract.

## The 12 checks (all must pass for HEALTHY)

1. **aeo_page_served** — GET /aeo/weight_loss/CHI → 200.
2. **aeo_cta_present** — that page body contains `buyer-cta` (CTA injected,
   not drifted off).
3. **sitemap_served** — GET /sitemap.xml → 200 + body has `aeo/`.
4. **robots_served** — GET /robots.txt → 200 + has `sitemap`.
5. **money_loop_apply_payurl** — POST hub /v1/buyers/apply (container IP)
   → response has payment.pay_url (solana: URL). PROBE INTERNALLY at
   10.118.155.218:8081 to avoid Cloudflare 403. Cleanup probe tenant after.
6. **outbox_flushing** — NOT(pending>20 AND sent_recent==0). Reads LIVE
   container DB via incus exec.
7. **subs_exist** — si_subscription row count > 0.
8-11. **unit_<name>** — empire-hub-8081, empire-mail-sender,
   empire-agent-founder-outreach, empire-agent-loop-closure — all checked
   via `incus exec empire-hub -- systemctl is-active` (they run IN the
   container, NOT on the host).
12. **tunnel_cloudflared** — host `systemctl is-active cloudflared-empire`.

## Output
- /root/feedback/qc_report.json: {ts, pass, fail, status, checks[]}
- stdout: [qc] HEALTHY/DEGRADED + per-check OK/FAIL
- on DEGRADED: revenue_notify.loop_stall("QC DEGRADED: <failing names>")

## Verification
```bash
/root/venv/bin/python3 /root/empire_os/empire_os/agents/qc_agent.py
# expect: [qc] HEALTHY pass=12 fail=0
systemctl list-timers empire-qc-agent.timer
# expect: next run in <=15 min
```

## Pitfalls (do NOT repeat)
- **Checking container units with host systemctl** — returns DOWN (false
  negative). Always `incus exec empire-hub -- systemctl is-active`.
- **Probing /v1/buyers/apply over public HTTPS** — Cloudflare WAF 403s
  repeated bot POSTs. Probe the container IP directly.
- **Reading host /root/empire_os/empire_os.db** — STALE mirror. Always incus
  exec the container for DB counts.
- **Wrong pay_url key** — response has payment.pay_url (a solana: string),
  NOT payment.url and NOT top-level pay_url. Check both payment.pay_url and
  top-level pay_url.
- **Probe tenant cleanup using wrong PK** — si_tenant has no `id` column;
  delete by tenant_id from si_subscription, not si_tenant rowid.
