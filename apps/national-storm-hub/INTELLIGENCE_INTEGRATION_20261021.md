# National Storm Hub ↔ EmpireOS — evidence-first intelligence bridge

Date: 21 October 2026
Status: isolated development implementation. **No public release or production service restart.**

## Existing systems reused

- National Storm Hub's existing `/api/predictor` already requests official NWS alerts, NWS point forecasts and the NOAA SPC Day 1 outlook. The new `reviewOfficialWeatherIntelligence` function projects those *same* responses into a source-state, provenance-classified consumer review. No new weather polling, CRM capture, analytics tracking or external model is introduced.
- The legacy `empire_os/storm_predictor.py` warning set remains the canonical historical origin of the deterministic four-warning classification. **Do not run that legacy Python agent inside a public request**: it can send notifications and call prospect callbacks.
- The existing `empire_os/storm_intelligence_runtime.py` produces a canonical OBSERVE snapshot under `/srv/empire_os/runtime/storm_opportunity/latest.json`. The new authenticated `/api/founder/storm-intelligence` reads only that original snapshot from the server filesystem and uses a strict, fail-closed safe projection. There is no new runtime daemon, scheduler, data source or database.
- The existing founder-only Revenue Pulse gate is reused via `lib/founder-auth.js`; no second login, new secret or public financial feed.
- All data handling is backed by EmpireOS **PostgreSQL EmpireDB**, never Supabase.

## Public intelligence contract

`/api/predictor?zip=75201` includes the existing `schema_version: nsh.predictor.v1` fields unchanged, plus `intelligence` with schema `nsh.intelligence_public.v1`. It reports:
- each source's status, one checked-at timestamp, forecast versus official issued warning truth class, and a warning-type count **only if the warning source is available**;
- missing sources and no warning records separately;
- explicit `damage_verified=false`, `homeowner_intent_verified=false`, `commercial_demand_verified=false` and `numeric_damage_risk=null`;
- no generated probability, home insurance assessment, buyer score or customer identity.

The existing `/predictor` page presents three source interpretations and the verification boundary. The wording is deliberately calm and removes the incorrect implication that a failed NWS warnings request returned no tracked warnings.

## Founder-only storm runtime

The existing private access key must be included in an `Authorization: Bearer ...` header. The storm route rejects absent/wrong keys; replies have no-store, Vary: Authorization and noindex headers. No raw events, candidate records, buyer IDs, tenant IDs, event IDs or evidence references can be returned.

The snapshot from **5 October 2026** is stale for launch readiness. The founder read model reports `status=STALE`, source date, and unknown current event/health counts. Even a fresh internal snapshot remains **EmpireOS-wide diagnostic evidence, not National Storm Hub buyer demand, home damage or revenue**.

The private `/founder/revenue-pulse` page shows this independent status beneath the existing canonical Revenue Pulse controls; unrelated revenue failures don't silently turn into weather knowledge.

## Gates still closed

- No automatic public notifications, outreach, customer enrichment, buying intent assignment, BSC funds or entitlement changes.
- No paid referral programme, payment activation, storm opportunity promotion or service-capacity claims.
- Real first-party, consented homeowner enquiries and verified contractor commitments are separate customer products, not assumed from NWS warnings.
- A fresh EmpireOS runtime observation must be rebuilt through the existing *authorized* storm owner process, not by treating the old snapshot as live or creating a new scheduler.
- The private shared founder key is a temporary access mechanism. Add stronger founder identity/Cloudflare Access before broader use.

## Verification

```bash
cd apps/national-storm-hub
npm test
NEXT_TELEMETRY_DISABLED=1 npm run build
```

Private preview tests: /, /alerts, /predictor, /founder/revenue-pulse and APIs; unauthenticated /api/founder/storm-intelligence must return 401 and contain no internal fields; valid authorization must return sanitized STALE status from the genuine EmpireOS snapshot. Outbound/revenue/payment gates unchanged. Public site should remain on its previous release until the founder reviews the isolated integration.
