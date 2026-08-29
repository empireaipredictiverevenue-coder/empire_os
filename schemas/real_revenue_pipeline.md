# Real Revenue Pipeline Schema
## Tables (verified in SQLite)

### crm_leads (9,764)
- lead_uid TEXT PK (e.g., ms_ee3001c948e9)
- source: market_sweep|serp_discovery|supabase_prospects
- business_name, contact_name, email, phone, metro, niche
- omega_score REAL, omega_tier TEXT (BRONZE/SILVER/GOLD)
- enrichment_score REAL, enriched INTEGER
- status: raw|enriched|contacted|qualified|sold
- icp_tier, icp_score, icp_fit_score

### lane_leads (4,666)
- lead_ref TEXT PK
- lane_id, niche, sub_niche
- omega_score, omega_tier

### si_firm_candidates (8) - HIGH VALUE
- legal_mass_tort: 3 prospects
- home_service: 5 prospects

### si_prospect_consent (4,907)
- consented prospects for outreach

### omega_prospects_unconsented (4,716)
- raw prospects needing consent

### buyer_leads (50) - registered buyers
- wallet, payout_per_lead, endpoint_url, hmac_secret

### si_invoice + si_outbox
- Settlement tracking (BSC USDT)
- Email delivery via Brevo

## Revenue Flow
1. Crawler/Scraper → crm_leads (raw)
2. Enrichment Waterfall (50+ sources) → enriched + email/phone
3. Omega Scoring → tier assignment
4. Campaign A (value-first) or B (enterprise)
5. Buyer claims lead → webhook → si_invoice created
6. Buyer pays USDT BSC → listener confirms → payout
7. Lead delivered via email/webhook → revenue recognized
