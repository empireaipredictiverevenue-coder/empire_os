# Empire Omega Neural Scout — Complete Integration Guide (ARCHIVED SPEC)

Archived from founder-provided spec 2026-08-29. Reference architecture for Neural Scout + Outcome-Based Marketing.

## Overview
Empire Omega = autonomous lead generation + outreach: Neural Scout (ML lead discovery/scoring), Outcome-Based Marketing (ROI-driven messaging, performance pricing), Lead Form Ads (Facebook/LinkedIn/Google), Real-Time Webhooks (AI call within 30s), Automated Outreach.

## Architecture flow
Lead Sources (Neural Scout organic / Lead Form Ads / Manual) -> leads.json -> Auditor (revenue-leak scoring 0-30) -> Outcome Marketing Engine (ROI estimate) -> Real-Time Webhook Processor (instant AI call via Vapi + outcome email via Resend) -> Portal Dashboard.

## Files
main.py (24h scout orchestrator), portal.py (Flask dashboard+webhooks :5000), researcher.py (ML query generator, learns from PAID leads), auditor.py (leak scorer), outbound.py (AI calling+email), outcome_marketing.py (ROI/perf proposals), lead_form_ads.py, realtime_webhook.py, leads.json.

## Env vars
Required: ANTHROPIC_API_KEY, VAPI_API_KEY, VAPI_ASSISTANT_ID, RESEND_API_KEY.
Optional: FACEBOOK_ACCESS_TOKEN, FACEBOOK_AD_ACCOUNT_ID, LINKEDIN_ACCESS_TOKEN, GOOGLE_ADS_API_KEY, SERPAPI_KEY, FROM_EMAIL=outreach@empireomega.ai, PORT=5000, LEADS_FILE, CYCLE_INTERVAL_HOURS=24.

## Webhooks
POST /api/webhooks/facebook/lead, /linkedin/lead, /google/lead, /generic/lead (any platform), GET /api/webhooks/health, GET /api/status, POST /api/cycle.

## Scoring (auditor.py)
Meta Pixel + no video ads +10 (High-Ticket Gap); no GTM+no Meta Pixel +5 (Total Tech Gap); load >3s +5 (Friction); modern site + Call Now -10. Advance threshold: score > 15. Whale = score > 20.

## Outcome-based pricing
Claude estimates annual revenue leak USD + recovery potential. Fee 20% of recovered. Guarantee: no recovery = no pay. KPIs: conv rate, AOV, CAC, rev/visitor.

## ML loop
Mark lead status=PAID in leads.json -> researcher.py analyzes PAID traits -> next cycle queries target similar prospects.

## Lead status values
PENDING, CONTACTED, PAID, QUALIFIED, CLOSED_WON, CLOSED_LOST.

## Empire OS v3 mapping (2026-08-29)
This spec maps to LIVE modules in empire_os/: neural_scout.py (empire-neural-scout.service, running), auditor logic in lead_scoring.py, outreach in outreach_agent.py + email_agent.py, webhooks in hub.py /v1/* routes, leads.json replaced by empire_os.db tables (crm_leads 9996 rows). Omega-AI remains SEPARATE business, not a lane client.
