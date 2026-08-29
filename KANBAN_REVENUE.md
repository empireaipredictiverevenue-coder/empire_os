# Empire OS v3 — Revenue Kanban

## 🎯 GOAL: First $100 Revenue → $10K/day

---

## 🔴 BLOCKED (Critical Path)

### [ ] Hunter.io API Key — Email Enrichment
- **Impact**: Without emails, outreach sends 0 messages
- **Action**: Get free key at https://hunter.io/api-keys (50 req/mo)
- **Config**: Add `HUNTER_API_KEY=<key>` to `.env` → push to empire-hub
- **ETA**: 5 min once key obtained

### [ ] Resend API Key — Email Sending
- **Impact**: Outreach falls back to webhook (no email sent)
- **Action**: Get free key at https://resend.com/api-keys (100/day)
- **Config**: `RESEND_API_KEY=re_...` + `SMTP_PASS=re_...` in `.env`
- **ETA**: 5 min once key obtained

### [ ] Onboard 3 Pilot Buyers — USDT Deposits
- **Impact**: $0 revenue until buyers deposit USDT
- **Targets**: 
  1. Plumbing contractor (Dallas/Atlanta)
  2. Roofing company (NYC/LA)
  3. General Contractor (Chicago/PHX)
- **Deposit**: 100 USDT each = 2,000 credits (Silver tier, $20/lead)
- **Webhook**: Register at `/v1/buyers/register` with delivery endpoint
- **ETA**: 1-2 days outreach

### [ ] Fund BSC Vault — Payout Liquidity
- **Address**: `0x1339b487046B0ad924a10c20b1791608EA8595a8`
- **Amount**: 500 USDT (covers ~100 lead payouts)
- **ETA**: 5 min once USDT available

---

## 🟡 IN PROGRESS

### [✅] Enrichment Webhook (port 9090) — RUNNING
- Endpoints: `/health`, `/enrich`, `/enrich/score`, `/enrich/email`
- Auth: `X-Enrichment-Secret: empire-enrich-secret-2024`
- Called by outreach_runner for email enrichment

### [✅] Outreach Runner v3 — DEPLOYED
- Dry-run tested: 25 prospects/cycle, 8 metros, branded HTML emails
- Delivery chain: webhook → Resend REST → Resend SMTP (port 465)
- Logs: `/root/empire_os/logs/outreach_log.jsonl`

### [✅] Neural Scout + Scout Intel — RUNNING (60s ticks)
### [✅] Crawler — RUNNING (13K leads/day)
### [✅] 9 LXC Containers — ALL RUNNING
### [✅] Hub Deep Health — ALL GREEN

---

## 🟢 READY TO EXECUTE (Once Blockers Cleared)

### [ ] Live Outreach Cycle
- Switch `--dry-run` off
- Monitor `/root/empire_os/logs/outreach_log.jsonl`
- Expect: 20-25 emails/cycle, 2-5 replies/day

### [ ] Buyer Onboarding Flow
- POST `/v1/buyers/register` with niche, metro, webhook_url
- Buyer deposits USDT to vault address
- Auto-credit: 100 USDT = 2,000 credits (Silver)

### [ ] Lead Delivery → Claim → Payout Loop
- Lead matched to buyer niche/metro
- Delivered via webhook + email + dashboard
- Buyer claims → credits deducted → USDT auto-payout to vendor
- BSC listener confirms → marks settled

### [ ] Scale to 5 Buyers → $10K/day
- Add HVAC, Electrical, Water Mitigation buyers
- Increase crawl rate to 25K/day
- Target: 500 delivered/day × $20 = $10K/day

---

## 📊 METRICS TO WATCH

| Metric | Current | Target (Week 1) | Target (Month 1) |
|--------|---------|-----------------|------------------|
| Leads/day | 13K | 15K | 25K |
| Emails sent/day | 0 | 500 | 2,000 |
| Replies/day | 0 | 5 | 50 |
| Buyers with USDT | 0 | 3 | 10 |
| Leads delivered/day | 0 | 100 | 500 |
| Leads claimed/day | 0 | 10 | 100 |
| **Revenue/day** | **$0** | **$2,000** | **$20,000** |

---

## 🚀 STARTUP COMMAND (Survives Laptop Close)

```bash
# On host (run once):
/root/empire_os/start_empire_os_full.sh

# Inside empire-hub container (auto-starts via systemd):
# - outreach_runner (hourly)
# - enrichment_webhook (port 9090)
# - buyer_hunter_agent (30min)
# - lead_sniper_agent
# - founder_outreach
# - bsc_listener
```

---

## 🔑 KEY FILES

| File | Purpose |
|------|---------|
| `/root/empire_os/.env` | All API keys (Hunter, Resend, SMTP, Webhooks) |
| `/root/empire_os/start_empire_os_full.sh` | Verified full startup |
| `/root/empire_os/empire_os/agents/outreach_runner.py` | Production outreach |
| `/root/empire_os/empire_os/agents/enrichment_webhook.py` | Email enrichment |
| `/root/empire_os/empire_os/agents/empire_enricher.py` | Intelligence engine |
| `/root/empire_os/REVENUE_SNAPSHOT_2026-07-26.md` | Revenue status |

---

## 🧠 AI LEAD MODE (When You're Away)

The system runs autonomously:
1. **Crawler** → 13K fresh leads/day into lane_leads
2. **Neural Scout** → Scores, tiers, assigns strategy (every 60s)
3. **Buyer Hunter** → Finds new buyers (every 30min)
4. **Outreach Runner** → Nurtures prospects → sends branded emails (hourly)
5. **Enrichment Webhook** → Provides emails + intelligence when Hunter fails
6. **BSC Listener** → Confirms USDT deposits → triggers credits
7. **Lead Sniper** → Matches leads to buyers → delivers via webhook
8. **Payout Agent** → Auto-pays vendors when leads claimed

**You only need to unblock**: Hunter key, Resend key, 3 pilot buyers, 500 USDT vault fund.