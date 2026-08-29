# Campaign A: Value-First Outreach
## Source: market_sweep (3,273 leads)
## Niche breakdown from DB
- mass_tort: 1,523
- plumbing: 327
- hvac: 324
- electrical: 194
- roofing: 183
- debt_relief: 143
- dental: 128
- real_estate: 127
- construction: 111
- landscaping: 100
- legal_services: 72
- pest_control: 26
- residential_roofing: 13
- roof_repair: 1
- solar: 1

## Strategy
- **Hook**: Free audit → $10 trial → USDT BSC payment → done-for-you implementation
- **Channels**: Email (Brevo), SMS (future), Portal (audit/{id})
- **Sequence**: 
  1. Day 0: Audit delivery + portal link
  2. Day 3: Case study + trial offer ($10 USDT)
  3. Day 7: Objection handling + social proof
  4. Day 14: Final notice + urgency
- **KPI**: Trial conversion > 5%, USDT settlement → MRR

## Lead Qualification
- Has phone: YES (all market_sweep have phone)
- Has email: NO (need enrichment waterfall)
- Omega scored: YES (44% avg, BRONZE/SILVER)
- ICP tier: unscored → needs enrichment

## Execution
- Enrichment waterfall first (50+ sources)
- Then email campaign via hub outbox /v1/outbox/enqueue
- Track via crm_leads.campaign_sent + enrichment_score
