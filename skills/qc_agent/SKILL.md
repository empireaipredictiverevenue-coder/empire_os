---
name: qc_agent
description: End-to-end quality-control probe for the Empire OS stack. Verifies AEO pages+CTA, sitemap/robots, money loop (/v1/buyers/apply pay_url), email outbox flush, unit health, and Cloudflare tunnel. Writes /root/feedback/qc_report.json. Runs every 15 min via empire-qc-agent.timer on HOST.
trigger:
  - "is the stack healthy / verify everything"
  - "qc check / health report"
  - scheduled: every 900s via empire-qc-agent.timer (host)
---

# SKILL: qc_agent

## What it does
Runs 12 health checks across the full stack and reports HEALTHY (all pass) or
DEGRADED (list of fails). Catches the exact failure classes seen in prod:
- AEO page served but CTA missing (inject drift)
- sitemap/robots unreachable (tunnel/hub down)
- money loop broken (apply returns no pay_url)
- outbox silently stalled (emails queued, 0 sent)
- critical units down (hub/mail-sender/founder-outreach)
- Cloudflare tunnel dead

## When to run
- Daemon via timer (empire-qc-agent.timer, host). Do NOT need to invoke manually.
- Manual: `python3 /root/empire_os/empire_os/agents/qc_agent.py` (host).

## Steps
1. HTTP probe public site: /aeo/<niche>/<metro> (200 + buyer-cta), /sitemap.xml,
   /robots.txt.
2. Money loop: POST /v1/buyers/apply to container hub (10.118.155.218:8081) →
   assert payment.pay_url present. Cleanup probe tenant after.
3. DB checks via `db_q()` which shells into the CONTAINER (incus exec) — never
   the stale host DB copy.
4. Unit checks: empire-* units via `incus exec empire-hub -- systemctl is-active`;
   tunnel via host `systemctl is-active cloudflared-empire.service`.
5. Write report JSON; alert on fail.

## Verification
- Run once → expect `[qc] HEALTHY pass=12 fail=0`.
- Inspect /root/feedback/qc_report.json.

## Pitfalls
- Money-loop probe MUST hit the container hub IP (10.118.155.218:8081), NOT the
  public URL — Cloudflare WAF 403s repeated bot-like POSTs, giving false FAIL.
- DB queries MUST run inside the container (host /root/empire_os/empire_os.db is
  a stale mirror). `db_q` uses `incus exec empire-hub -- python3 -c`.
- unit_active(u, host=False) checks the CONTAINER; host=True for tunnel only.
- Probe tenant cleanup uses si_subscription.tenant_id + si_tenant.tenant_id
  (si_tenant has no 'id' column — don't use it).
