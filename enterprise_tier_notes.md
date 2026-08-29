# Enterprise Tier Launch — White-Label Omega OS (REVENUE)
Status: PLAN ONLY → BUILD REQUIRED. No `enterprise_` code exists. `si_firm_candidates` = 5 home-service (roof/hvac/plumb), NOT law. Web (Firecrawl) down.

## What exists (verified)
- Skill: `empire-os-enterprise-tier-launch` (pricing $5K/mo + $3/lead · 12-mo · white-label · 8-dim Omega + tiered $8-45/lead · buyer pool)
- `enterprise_campaigns`: 1 row (budget/targets set)
- `enterprise_leads_campaign`: 1 row (monthly target / conversion set)
- Revenue engine (`revenue_plan.py`) + live dashboard endpoint (`revenue_dashboard.py`) — confirms $2,189 MRR, 0 settlements, 563 subs

## What's MISSING (build list)
1. White-label Omega scoring module (custom weights, branded funnel events, client subdomain)
2. Tiered pricing assignment engine (BRONZE/SILVER/GOLD/PLATINUM → $8/$15/$25/$45 per lead, 3× disaster)
3. Dedicated buyer pool routing (exclusive, no self-serve overlap)
4. Real law-firm prospects (DB has 0; source via direct outreach / manual CSV / partner referral — web down)
5. Sales outreach asset (email sequence from skill Section 6 — ready to parameterize)

## Executable now (without web / without code)
- `[DONE]` Outreach email sequence drafted from skill (Day 1/4/7/11). File: `/root/empire_os/enterprise_outreach_sequence.md`
- `[DONE]` Target framework (10 categories from skill Section 7): regional, multi-state PI, NEC, Roundup, AFFF, 3M earplugs, talc, Philips CPAP, mixed-tort, tech-forward
- `[PENDING]` Load real prospect CSV into `si_firm_candidates` (vertical=`legal_tort`) once sourced manually
- `[PENDING]` Build white-label module (new `empire_os/enterprise_tier/` package)
- `[PENDING]` Wire outreach via `mail_sender` (Brevo, live vault — already fixed) when prospects loaded

## Revenue projection (skill Section 10, conservative)
- 3 pilot clients × $6,500/mo = $19,500 / 90 days
- Year 1 (3 clients): $234,000; Year 2 (50 clients): $3.9M annualized
- Requires 1st SELL, then onboarding (3-week), then go-live → MRR dashboard updates

## Critical dependency
Buyer pays = `bsc_listener` collects BSC USDT → `si_settlements`. Currently 0 settlements. Enterprise tier only funds when buyers actually pay for delivered tiered leads — mail flush is prerequisite, not sufficient. Revenue loop: score → tier → match → deliver → buyer payment → settlement → MRR.
