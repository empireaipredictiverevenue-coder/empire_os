# Marketing Plan A: Value-First Outreach
## Target: 3,273 market_sweep leads (all have phone, need email enrichment)

### Funnel Stages
| Stage | Leads | Action | Tool | KPI |
|-------|-------|--------|------|-----|
| Raw | 3,273 | Enrichment waterfall | enrichment_v2.py | Email found > 40% |
| Enriched | ~1,300 | Omega scoring | omega_scoring.py | Tier distribution |
| Scored | ~1,300 | Campaign send | mail_sender.py (hub outbox) | Open rate > 25% |
| Contacted | ~325 | Portal visit | /audit/{id} | Click rate > 10% |
| Trial | ~33 | USDT $10 payment | BSC listener | Conversion > 5% |
| Paid | ~2-3 | Implementation | Done-for-you | MRR +$2K |

### Email Templates (Empire OS dark theme: cyan/blue/neon-green/dark)
**Template 1 - Audit Delivery (Day 0)**
- Subject: "Your {niche} audit for {metro} - {business_name}"
- CTA: "View your audit → /audit/{lead_uid}"
- Brand: Dark bg, cyan headers, neon-green CTAs

**Template 2 - Case Study + Trial (Day 3)**
- Subject: "How {similar_business} got 3x leads in {metro}"
- CTA: "Start $10 trial → /audit/trial"
- Payment: USDT BSC to 0x1339b487046B0ad924a10c20b1791608EA8595a8

**Template 3 - Objection Handling (Day 7)**
- Subject: "Still paying $300/lead on {platform}?"
- CTA: "Compare → /audit/trial"

**Template 4 - Final Notice (Day 14)**
- Subject: "Closing {business_name} audit access"
- CTA: "Last chance $10 trial"

### Enrichment Waterfall (50+ sources - implemented in enrichment_v2.py)
1. Tier 1 (5): website_scraper, ddg_search, bing_search, google_search, whois
2. Tier 2 (15): bbb, yellowpages, chamber, state_license, capterra, angie, homeadvisor, porches, thumbtack, houzz, buildzoom, manta, superpages, citysearch, dexknows
3. Tier 3 (1): google_search
4. Tier 4 (12): financial, intent, buy_intent, market, tech, social, review, hiring, ad, permit, news, websize signals
5. Tier 5 (27): paid stubs (clearbit, hunter, apollo, etc.)

### Automation
- Cron: enrichment every 6h (crawler timer)
- Campaign send: daily batch 50 via hub outbox
- Tracking: crm_leads.campaign_sent, enrichment_score, status
