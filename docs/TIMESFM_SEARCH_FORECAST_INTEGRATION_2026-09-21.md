# TimesFM Search Forecast Integration — 2026-09-21

## Role in EmpireOS

TimesFM is integrated as a shadow forecasting backend, not a source of truth and not a new standalone product.

Flow: Google Search Console daily observations -> impressions + clicks -> deterministic Empire baseline -> optional TimesFM 2.5 shadow forecast -> projected horizon impressions/clicks/CTR -> Trend/Regime, Search Growth Command and CRM/revenue attribution.

Observed Search Console data stays canonical truth. TimesFM values are modeled forecasts only; they cannot create actuals, revenue, payment evidence, external actions or accounting entries.

## Current implementation

- empire_os/timesfm_shadow.py: fail-closed optional TimesFM 2.5 provider, lazy load, validation, shadow-only authority.
- empire_os/search_traffic_forecast.py: daily Search Console aggregation, baseline comparison, TimesFM shadow comparison, horizon impressions/clicks and derived CTR.
- GET /v1/search/search-console/daily
- GET /v1/search/forecast/traffic
- Search Growth Command exposes click_impression_forecast and separates deterministic traffic-forecast readiness from TimesFM availability.

## Activation

TimesFM is intentionally not installed or activated on the current EmpireOS application server. That older CPU-only host should remain focused on business orchestration. Activation is fail-closed and requires EMPIRE_TIMESFM_SHADOW_ENABLED=true and EMPIRE_TIMESFM_SHADOW_APPROVED=true. Recommended deployment target: a separate inference worker/node.

## Version / license rule

For commercial Empire use, target TimesFM 2.5 pretrained weights. Google Research states source code and weights through 2.5 remain Apache-2.0. TimesFM 3.0 pretrained weights are currently under a separate non-commercial license, so 3.0 remains R&D-only unless licensing changes or a commercially permitted model is used.

Official repository: https://github.com/google-research/timesfm

## Next forecast series

Leads acquired, qualified opportunities, buyer-review readiness, delivered outbound, replies, commercial conversations, terms, verified payments, recognized revenue, realized GP, storm-trigger demand, backlink/referring-domain velocity, AI citations and brand mentions.

Every series must preserve observed/modelled separation and be backtested before predictions influence priority or resource allocation.
