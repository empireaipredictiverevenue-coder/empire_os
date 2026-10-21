# National Storm Hub — First Public Product Slice (Private Candidate)

Standalone consumer-facing **Next.js** app; not part of the Empire AI corporate site's route tree.

## Implemented

### Evidence-first depth candidate (2026-10-21)
- `/predictor`: working ZIP-first Storm Predictor; combines official NWS point forecast, active NWS alerts and NOAA SPC Day 1 categorical polygon query; no property damage claims.
- `/api/predictor?zip=75201`: 3 independent provider checks with source freshness, statuses and fail-closed partial/unavailable conditions.
- `/research`: public source register and limitations of weather forecasts, historical records, storm alerts and federal sources.
- `/recovery`: homeowner before/during/after safety-first guide with hazard-specific advice and primary source links.
- Homepage links to new tools, deep research and safety guidance. Existing homepage and state pages are retained.
- The old `empire_os/storm_predictor.py` NWS-warning classification set is mirrored in `lib/predictor.js`; the side-effecting agent daemon, notifications and CRM are NOT called from the public app.
- Tested with Dallas (75201), Miami (33101) and Anchorage (99501); non-CONUS outlook appropriately labels itself out-of-coverage.

**This section describes a development candidate and is not live until the independent release is reviewed and deployed.**

## Implemented

- National brand homepage with responsive weather-themed visual design
- Distinct Texas and Florida state-hub preview pages with original preparedness guidance and authoritative local sources
- State selection for all 50 states plus DC
- Live read-only public NWS alert list by state, including source links and timestamps
- ZIP lookup using Zippopotam.us location centroids, followed by official NWS point lookup
- Distinct source-unavailable vs genuine zero-active-alert states
- Browser-local Storm Passport: save one area, progress on preparedness tasks, bookmark linked weather records, export as JSON and clear records
- Non-commercial safety and preparedness guidance; Storm Hub Pro is visibly **concept only**
- 5 source/normalization and regional-content unit tests; no API keys, no paid data sources
- Server route never infers property damage, buyer intent or revenue

## Run locally on the EmpireOS server (isolated worktree)

```sh
cd /home/ubuntu/empire_worktrees/national_storm_hub_build_20261021/apps/national-storm-hub
npm ci
npm test
NEXT_TELEMETRY_DISABLED=1 npm run build
npm start
```

By default the app serves on port **3128**. To view privately, use an authorised SSH tunnel or deployed preview. **Do not change production DNS or open firewall ports solely to preview this candidate.**

For a developer-only quick build on the EmpireOS machine, a temporary symlink to an already installed sibling `node_modules` was used and `next build --webpack` avoids Turbopack's cross-worktree symlink boundary. A clean deployment should use the checked-in package lock and normal `npm ci`, not copy the symlink.

## Key endpoints

- `GET /` — responsive National Storm Hub and Storm Passport
- `GET /api/alerts?state=TX` — public NWS current alert records in Texas
- `GET /api/alerts?zip=75201` — ZIP centroid lookup then NWS point alerts
- `GET /states/texas` — Texas severe-weather preparedness resources
- `GET /states/florida` — Florida hurricane preparedness resources

The server should set a real contactable `STORM_HUB_NWS_USER_AGENT` string at deployment in keeping with NWS best practices. The current preview uses a labelled fallback. Requests are read-only; official NWS feeds have availability and licensing/use terms to verify before publication.

## Privacy & factual limits

- **No account system, cloud vault, uploaded files, lead sale, call routing or contractor enrolment yet.**
- Storm Passport data is stored on the user's own browser in `localStorage`, not in EmpireDB or the CRM; the interface labels it as a local preview.
- ZIP lookup calls a third-party public geocoding service to obtain approximate latitude/longitude. A ZIP is not an exact property location.
- Alerts can expire or be delayed. The UI shows timestamps and does not replace emergency warning services.
- The animated globe and radar visualisation are expressly labelled illustrations, not official geographic warning boundaries.
- Page sets `noindex` until public-ready approvals, privacy/accessibility checks, domain reconciliation and release.
- Storm Hub Pro is a concept, not a functioning subscription or buyer marketplace.
- No billing, funds, marketing automation or live outbound.

## Source reuse

Uses a separate front end while preserving the canonical EmpireOS storm-intelligence owner modules:
`empire_os/storm_predictor.py`, `empire_os/storm_intelligence_runtime.py`, `empire_os/storm_opportunity_bridge.py`. This MVP does not connect to internal prediction artifacts or enable downstream opportunity execution.

## Release gates

Before public domain changes: independent NWS/ZIP source validation, accessibility on mobile, consumer privacy/legal pages, first-party consent, monitoring/error states, security review, HTTPS, DNS/old hosting audit, release plan and founder approval. Pro/lead exchange requires separate buyer and legal gates.
