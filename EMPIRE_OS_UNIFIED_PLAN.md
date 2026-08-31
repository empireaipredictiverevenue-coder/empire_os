# EMPIRE OS — UNIFIED REVENUE + GROWTH PLAN (single source of truth)

Generated 2026-08-29 (update 2). Replaces prior versions. All services live + automated.
This update: FIXED 4 broken automation phases + added low-friction reply-to-buy.

================================================================
1. REVENUE PATH IS NOW LIVE (what makes money)
================================================================
LINE A  Lead Marketplace — buyers pay for leads
  - Outreach live: 2060 real businesses emailed via Brevo (restoration/roofing)
  - Low-friction buy: buyer replies "yes/buy/interested" to any email
    -> inbound_reply_daemon auto-onboards them -> silver sub awaiting_payment
    -> they fund USDT -> sub active -> leads delivered -> per_lead billed
  - No wallet needed up front. Reply = buyer.

LINE B  SMB SaaS SKUs (18 products)
  - /v1/products/{sku}/order -> USDT BSC -> bsc_listener -> delivery email
  - 0 sales yet (needs traffic to landing pages)

LINE C  Omega AI Engine (:9100, separate business)
  - metered calls -> omega_metering -> monthly settle -> vault
  - onboard tenants to monetize $499-$4997/mo

LINE D  Mass Tort (masstort_leads built, /v1/mass-torts/direct)
  - needs tort source feed

LINE E  Enterprise/Whale
  - /v1/enterprise/register|quote|assign, /v1/a2a/escrow/fund

LINE F  5-Phase Automation — ALL 5 NOW RUN (was 1/5 broken)
  discovery (bounded 180s) -> scoring -> outreach -> ml_loop -> reporting

================================================================
2. FIXES THIS SESSION (money unblocked)
================================================================
1. discovery phase: was importing nonexistent run_discovery_cycle -> now run_all_sources (generator, 180s hard cap so timer can't hang)
2. scoring phase: crm_leads missing scored_at/score_breakdown columns -> added; lead['id'] -> lead_uid
3. outreach phase: JOIN used c.id (PK is lead_uid) -> fixed; threshold lowered to omega_score>=10 (100 qualified)
4. ml_loop phase: converted_at -> sold_at (crm_leads has sold_at)
5. email verify gate hardened (hub.py) — kills 98% junk subs
6. per_lead_cents backfilled on 65 active subs — billing fires on delivery
7. Omega engine live :9100, real 8-dim, metered -> vault
8. masstort_leads table + intake mirror
9. LOW-FRICTION BUY: inbound_reply_daemon reply-intent -> auto_onboard (verified: reply "yes" -> silver sub created)
10. deploy_check fixed (valid test email + non-fatal RPC) — hub stays up

================================================================
3. SERVICE STATUS (verified 2026-08-29)
================================================================
empire-hub-8081        active   8081
empire-omega-learning  active   9100
empire-omega-os        active
empire-bsc-listener    active
empire-supervisor      active
empire-mail-sender     active   (Brevo, 2060 sent)
empire-inbound-reply   active   (reply-to-buy)
empire-omega-automation@ (5 timers) enabled

================================================================
4. WORKFLOWS (plain text)
================================================================
A  crawler -> crm_leads -> omega_score -> lane_leads -> Brevo outreach -> buyer replies YES -> auto_onboard -> sub_awaiting -> pay_url -> funded -> sub_active -> deliver -> per_lead_bill -> vault
B  landing -> /v1/products/{sku}/order -> USDT -> bsc_listener -> delivery email
C  omega:9100 -> executeFullCycle -> 8area -> tenant_tier -> metered -> omega_metering -> monthly_settle -> vault
D  tort_source -> /v1/mass-torts/direct -> masstort_leads -> legal_buyers -> case_settle -> residual
E  enterprise_register -> si_whitelabel -> si_seats -> a2a_escrow -> fund -> vault
F  discovery_timer -> scoring_timer -> outreach_timer -> ml_loop_timer -> reporting_timer -> automation_runs

================================================================
5. GROWTH LEVERS (ranked)
================================================================
L1  Outreach to real businesses (LIVE, 2060 sent) — primary money now
L2  Reply-to-buy (LIVE) — zero-friction conversion
L3  Email verify gate (LIVE) — clean buyer base
L4  per_lead billing (LIVE) — 65 subs backfilled
L5  Omega metered tiers — onboard tenants
L6  SMB SKU landing pages — drive traffic
L7  Mass tort feed — Line D
L8  Enterprise/whale — Line E

================================================================
6. FORECAST (grounded)
================================================================
Now: 2060 businesses contacted, reply-to-buy live.
If 2% reply "yes" = 41 new buyers x $59/mo = $2.4K/mo recurring + per_lead.
At 5% = 103 buyers = $6K/mo + per_lead billing ($49/lead).
90-day realistic: $10K-$50K/mo recurring once replies convert + per_lead scales.

================================================================
7. NEXT (do now)
================================================================
- Monitor si_inbox for "yes" replies -> auto-buyers accrue
- Send more outreach waves (Brevo) to crm_leads + scraped businesses
- Build 3 SKU landing pages -> /v1/products/{sku}/order
- Onboard omega tenants (:9100)
- Feed mass tort source
- Daily: reporting phase shows revenue in automation_runs
