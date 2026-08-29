# End-to-End Automation Workflow

## 1. Lead Ingestion (Crawler/Scraper)
- **Trigger**: Cron every 6h (empire-crawler-runner.timer)
- **Sources**: permits, licenses, gbp, yelp, reddit, gmaps, sos_business, places_business, realestate_intent
- **Output**: crm_leads (raw) + lane_leads
- **Rate limit**: 100 burst / 10 sec on hub /v1/leads/direct

## 2. Enrichment Waterfall
- **Trigger**: New lead in crm_leads (enriched=0) OR cron every 6h
- **Process**: 50+ source cascade (enrichment_v2.py)
- **Concurrency**: 20 agents max, PRAGMA busy_timeout=30000
- **Output**: email, phone, website, social, enrichment_score
- **Cache**: 7-day TTL per source

## 3. Omega Scoring
- **Trigger**: Enriched lead (enrichment_score > 0)
- **Process**: 8-dim scoring (omega_scoring.py)
- **Output**: omega_score (0-1), omega_tier (BRONZE/SILVER/GOLD), omega_grading
- **Lane assignment**: lane_leads table

## 4. Campaign Routing
- **BRONZE/SILVER** → Campaign A (Value-First)
- **GOLD** → Campaign B (Enterprise)
- **Legal/High-value** → Direct founder outreach

## 5. Campaign Execution
- **Hub outbox**: /v1/outbox/enqueue (Brevo API)
- **Batch**: 50/day per campaign
- **Tracking**: campaign_sent=1, status=contacted
- **Portal**: /audit/{lead_uid} for audit delivery

## 6. Conversion & Settlement
- **Trial**: $10 USDT BSC → vault 0x1339b487046B0ad924a10c20b1791608EA8595a8
- **Listener**: empire-bsc-listener.service (PID watchdog)
- **Invoice**: si_invoice created on claim, paid on USDT confirm
- **Payout**: buyer_webhook_integration → payout_batch

## 7. Revenue Recognition
- **MRR**: $2189 current (verified)
- **Tracking**: si_invoice.paid_at, payout_per_lead
- **Dashboard**: empire_stats.py + revenue_dashboard.py

## Monitoring & Self-Heal
- **Health**: /v1/health/deep (hub, DB, services)
- **Self-heal**: empire-os-self-heal (orphan cleanup, lock recovery)
- **Guardian**: guardian_agent.py (metrics, alerts)
- **Cron**: empire-crawler-runner.timer, empire-enrichment.timer, empire-campaign.timer