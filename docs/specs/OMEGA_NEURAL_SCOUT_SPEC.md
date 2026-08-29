# Empire Omega Neural Scout — Complete Integration Guide (SPEC, pasted 2026-08-29)

Status: DESIGN SPEC. Partially implemented in Empire OS. Not the same thing as Omega AI (Philip's separate business).

## What maps to LIVE Empire OS modules

| Spec component | Live module | State |
|---|---|---|
| Neural Scout (lead discovery + scoring) | agents/neural_scout.py, scout_intel.py + empire-neural-scout.service | LIVE |
| Auditor (leak scoring 0-30) | agents/lead_grader.py, site_audits table, grader ledger | LIVE (different scoring model) |
| Outcome marketing (ROI estimation) | agents/outreach_agent.py, sequence_engine.py, outbound_campaigns | LIVE (email via Brevo not Resend) |
| AI calling (Vapi) | NOT in Empire OS core — Omega AI territory (separate business) | OUT OF SCOPE for OS |
| lead_form_ads / FB-LI-GG ingestion | lead_intake.py, funnel_intake.py, homeowner_pipeline | PARTIAL — webhook adapters exist, FB/LI/GG platform tokens NOT configured |
| Real-time webhook + 30s AI call | inbound_reply_daemon.py, enrichment_webhook.py | PARTIAL — webhooks live, instant AI calling not wired |
| leads.json central DB | REPLACED by SQLite empire_os.db + Supabase | SUPERSEDED |
| Portal dashboard | dashboard_v2.py | LIVE |

## Env vars spec requires (NOT all set): FACEBOOK_ACCESS_TOKEN, LINKEDIN_ACCESS_TOKEN, GOOGLE_ADS_API_KEY, VAPI_API_KEY, VAPI_ASSISTANT_ID, SERPAPI_KEY (Empire OS uses self-hosted Serper instead).

Original doc preserved below for reference.
---
[Original pasted doc: Empire Omega Neural Scout integration guide — architecture, webhook endpoints /api/webhooks/{facebook,linkedin,google,generic}/lead, leads.json schema, scoring logic, outcome-based marketing, performance pricing, 30-second AI call flow, dashboard features. Full text held in session; key deltas captured above.]
