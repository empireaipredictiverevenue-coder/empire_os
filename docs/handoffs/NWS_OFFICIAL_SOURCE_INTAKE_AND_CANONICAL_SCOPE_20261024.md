# EmpireOS NWS official-source intake — bounded integration handoff

**24 Oct 2026. Branch:** feature/nws-official-source-provenance-20261024
**Owner:** original storm source + Source Intelligence + Core + EmpireDB
**Parent:** 233b48783. No new platform, tables, services or spending.

## Verified provider policy
NOAA National Weather Service API official docs:
https://www.weather.gov/documentation/services-web-api
and https://www.weather.gov/documentation/services-web-alerts
The NWS alerts API is public/free, with reasonable rate limits; use an
identifying User-Agent, JSON/GeoJSON, bounded GET, no key needed. Active
state filter documented at /alerts/active?area=IL.

## Genuine implementation, NOT a duplicate ingestion system
New file: empire_os/nws_official_source_provenance.py.
- Reuses the original storm_predictor.NWS_ALERTS_URL, StormEvent,
  spatial_physical_adapters.event_evidence_from_storm_event,
  original lead_sources.storm_alerts.UA and universal_source_custody_review.
- One explicit, opt-in public read: fetch_nws_active_alerts_once(
  enable_official_read=True). No automatic polling, retry loop, new timer,
  Redis stream, department queue, alerts, Telegram, on_strike callback,
  CRM, EmpireDB or HTTP payments, no provider SDK or paid compute.
- Pinned endpoint and one-state filter. No user URLs, redirects, proxy
  credentials, arbitrary providers or parameter injection. One timeout-8
  HTTPS GET; at most 2MB read and 80 features. Over-limit fails CLOSED.
- Validates dated, allowlisted NWS event fields with the ORIGINAL spatial
  evidence parser; ignores free-text headlines/description bodies, extra
  provider fields and geometry. Only hashed alert identity is forwarded to
  the universal source review. Provider events or PII are never persisted.
- Dedupe and provenance review returns only source reference counts,
  safe redacted fingerprints, source-host and separate unknown-rights,
  source-custody, tenant/entity, buyer and revenue blockers.
- review_nws_to_existing_canonical_scope joins source references to the
  ORIGINAL resolve_tenant_entity_binding read, using only an owner-supplied
  authenticated, restricted, read-only cursor plus canonical tenant and
  entity identifiers. That confirms binding only. It **never** claims the
  affected location is connected to that entity, that the NWS alert proves
  storm damage, or that a weather alert is an economic market-gap signal.
  Original Economic Signal Fabric stays authoritative, no synthetic type
  such as market_gap or revenue_leak is generated.
- Any downstream entity attribution requires independently grounded
  canonical source registry, spatial overlap/subject custody and genuine
  commercial evidence, not string matching areaDesc.

## Actual live read evidence (one-off, not production activation)
1. First public national active alerts GET returned payload exceeding the
   2MB maximum; correctly HELD. We kept the cap and switched to fixed
   state-level pilot, using the published NWS area parameter.
2. Exactly one Illinois live GET using the fixed
   https://api.weather.gov/alerts/active?area=IL endpoint succeeded and
   passed the read-only evidence review:
   - HTTP source response observed: YES
   - Structurally accepted alert references: 0 (no active alerts in
     that particular response)
   - Source shape rejects: 0
   - Database/CRM/Redis writes: NO
   - Customer contact, marketing, notifications or payment: NO
   - Tenant source provenance, buyer demand, property damage, revenue:
     NOT VERIFIED
   Zero alerts here says nothing about national alerts or regional buying
   demand. No auto-polling or alert pipeline was activated.

## Explicit original-owner next step
The original Core & Data Cloud owner can review the exact source adapter,
validate NOAA ToS, canonical source mapping and regional data provenance,
and approve one safe release if commercially useful. For a record-bearing
fixture or real alert, first read canonical tenant business entity binding
and separately prove source->subject and spatial linkage. Only then should
the original economic-signal owner decide whether a distinct, real
economic indicator exists; a weather alert alone cannot pass that gate.
No pre-emptive StormProductActivation, call routing, buyer acquisition,
outbound, model confidence claims, payment or forecasting authority.

For repeatable verification:
```bash
cd /home/ubuntu/empire_worktrees/nws_official_source_provenance_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  -p no:cacheprovider tests/test_nws_official_source_provenance.py \
  tests/test_universal_source_custody_review.py \
  tests/test_economic_signal_fabric.py \
  tests/test_economic_signal_tenant_binding.py \
  tests/test_predictive_revenue_prime.py \
  tests/test_predictive_edge_depin_governance.py
```

**Release posture: isolated branch, OBSERVE, merge held for original
owner and concurrency reconciliation.** Production EmpireDB, Smart CRM,
PRIME, original source providers, local inference and pgBackRest untouched.
Rollback is dropping/reverting the isolated feature; no new persistent
resources were created.
