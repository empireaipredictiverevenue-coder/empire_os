# Empire Omega OS — Complete Deployment Guide (ARCHIVED SPEC v1.0, April 2026)

Founder-provided deployment guide archived 2026-08-29. 6-pillar Omega OS architecture.

## The 6 Pillars
1. Scout — ML search query lead discovery
2. Auditor — site revenue-leak analysis
3. Messenger — personalized email outreach
4. Ledger — payments + conversions (Solana SOL+USDC)
5. Creative — AI video generation
6. Affiliate — commission tracking + payouts

## Stack (spec)
React 19 + Tailwind 4 + tRPC frontend; Express 4 + Node 22 tRPC backend; MySQL/TiDB + Redis; Python services; Solana payments; Docker/K8s/Nginx; Prometheus/Grafana/ELK.

## Empire OS v3 live mapping (2026-08-29)
- Pillar 1 Scout: neural_scout.py (service running)
- Pillar 2 Auditor: lead_scoring.py + aeo_checker.py
- Pillar 3 Messenger: mail_sender.py (Brevo) + outreach pipeline
- Pillar 4 Ledger: BSC USDT listener (empire-bsc-listener.service) — spec said Solana; v3 standard = BSC USDT to vault 0x1339b487046B0ad924a10c20b1791608EA8595a8
- Pillar 5 Creative: avatar pipeline + video_ads_engine_agent.py
- Pillar 6 Affiliate: affiliate.py module
- Frontend: hub.py serves dashboard at :8081 (FastAPI+HTMX dashboard_v2), not React/tRPC
- Solana wallet ops: solana-batched-payouts + solana-v0-tx-solders skills; integrations.py CRM sync patterns (HubSpot/Salesforce/Zapier) archived for reference

## Env vars from spec (reference)
DATABASE_URL, SOLANA_*, SMTP_*, HUBSPOT_API_KEY, SALESFORCE_*, ZAPIER_WEBHOOK_URL, VAPI_API_KEY, VAPI_ASSISTANT_ID.

## Solana payment ops (spec reference)
solana-keygen keypair; invoice create/check via solana_payments.py; USDC mint EPjFWdd6aufhSyq6JSCEwNMZKZ4rWoSbe2stgBRL2v7i... (mainnet); Jupiter swap SOL->USDC.
