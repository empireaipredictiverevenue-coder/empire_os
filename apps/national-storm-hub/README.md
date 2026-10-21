# National Storm Hub — First Public Product Slice (Private Candidate)

Standalone consumer-facing **Next.js** app; not part of the Empire AI corporate site's route tree.

## Interactive premium hero and hazard sliders (private candidate, 2026-10-21)

- Removed the old decorative globe from the rendered homepage.
- Implemented **native Three.js** in `components/StormfrontScene.jsx`, with original procedural layered terrain, stormfront ribbons, yellow signal beacons, pointer-responsive viewpoint and gentle scroll response.
- **Conceptual weather art only**: this cannot be confused with official NWS alerts, observed storm tracks, geographic warning boundaries, proprietary forecast accuracy or confirmed house damage. Existing official NWS/SPC data continues to power the actual Atlas and Predictor.
- Graceful static atmospheric fallback when WebGL is unavailable, user prefers reduced motion or viewport is small. Three.js loads asynchronously outside initial page rendering; no external 3D asset download is required.
- Three-slide homepage journey with arrows, pagination, horizontal touch swipes, restrained 9-second automatic advance, focus/hover pause and reduced-motion support. Persistent ZIP search and genuine Predictor/Alerts/Passport navigation.
- Four-slide editorial Hazard Lens selector with source-linked Hail/Wind, Flood, Hurricane and Tornado guides. This is *not* a real-time risk model.
- Existing black / red / white / safety-yellow token system, themed buttons and founder/alerts/predictor pages are preserved. No change to production service or Cloudflare DNS.
- Dependency pinned in the application package and lockfile: `three@0.180.0`.

## Premium emergency design comparison — Jack workflow (private candidate)

- Distinct research references and `DISCOVER → SHAPE → DESIGN → MAKE → REVIEW → PROVE` workflow mapped to the existing **Empire Design Studio** candidate; no duplicate skill or agent.
- Two visual directions, **Signal Noir** and **Command Red**, using black, emergency red, white and safety yellow throughout the existing frontend. Source warning status and property-damage semantics remain unchanged.
- `NEXT_PUBLIC_NSH_DESIGN_LAB=1` at **preview build time** shows an in-page direction switch; absent in normal builds. Review only; not a public design configurator.
- Chrome screenshot evidence at 1440/820/390/320 and unit/build checks required before release. No 3D weather engine or official alert-boundary map has been added by a color-theme change.
- The actual production National Storm Hub service/DNS is not changed by this isolated branch.

## Impeccable-informed UI polish (private candidate, 2026-10-21)

- Reuses the existing Hermes Impeccable catalogue **reference** and records actual audience, brand, evidence boundaries and design direction in first-party `PRODUCT.md` and `DESIGN.md`.
- Improves responsive navigation and introduces a verified-source status strip using the homepage's **existing** NWS Atlas request; no extra polling or data provider.
- Distinguishes loading, zero alerts, unavailable source and returned records; unknown weather conditions are never presented as safe.
- The full Impeccable CLI and agent commands have **not** been installed or executed; this is a bounded manually implemented visual and UX pass. A browser screenshot audit remains required before visual production signoff.

## Website alerts and private Revenue Pulse (2026-10-21)

- Public `/alerts` — state, ZIP and Storm Passport area lookups; five-minute NWS rechecks while page remains open; optional browser notifications only for new severe warnings after permission; never a substitute for official emergency warning channels.
- Private `/founder/revenue-pulse` — founder-key protected company-wide EmpireOS Pulse V3 and observed conversion-gap alerts, with automatic refresh and optional in-session pop-ups.
- Private `/api/founder/revenue-pulse` — environment-key authentication, no-store headers, unknown National Storm Hub tenant financial metrics until genuine source-ledger evidence is connected.
- Neither the visitor dashboard nor the private founder dashboard triggers customer outreach, sales automation, fund movement or chat reminders.

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
