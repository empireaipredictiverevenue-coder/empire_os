# National Storm Hub — First Public Product Slice (Private Candidate)

Standalone consumer-facing **Next.js** app; not part of the Empire AI corporate site's route tree.

## Homeowner journey slider (private preview, 2026-10-21)

- Replaces the three static **Prepare / Understand / Recover** cards with a full-width, high-contrast editorial slider. Each of the three stages has its own restrained atmospheric artwork, practical checklist and two purposeful links, without copying the Empire AI corporate homepage or adding another globe.
- Includes previous/next buttons, explicit stage selectors, horizontal swipe on touch devices, keyboard left/right on controls, focus/hover pause, and optional gentle advance only while on-screen and only when the visitor has not interacted. The visitor's reduced-motion preference is respected.
- Source-linked actions lead to Storm Passport, current official NWS alerts and recovery guidance, with Ready.gov/weather.gov external references. Nothing infers home damage, current storm severity or paid contractor readiness.
- Tested **31 website unit tests**, Next.js production build and actual Chrome click interactions at **1440, 820, 390 and 320 pixels**, with no horizontal overflow or browser JS errors. Mobile state transitions and their links were verified.
- Read-only preview uses port `3165` on loopback; public `nationalstormhub.com` remains unchanged pending founder review.

## Reusing EmpireOS intelligence systems (private integration candidate)

- The existing National Storm Hub public `/api/predictor` now includes a deterministic `intelligence` evidence review based on the **same** official NWS warning/forecast and SPC requests. No second feed, LLM inference or independent background poller is created.
- The private Founder Console reads the **existing** `/srv/empire_os/runtime/storm_opportunity/latest.json` through `/api/founder/storm-intelligence`, guarded by the existing founder-only access key and no-store headers. It does not expose raw event, tenant, buyer or opportunity records.
- The actual runtime snapshot observed on October 21 was from **October 5**. The private console explicitly displays **STALE**; current candidate counts and event metrics stay unknown.
- Public forecasts, NWS warnings and internal commercial readiness remain distinct. No inferred property damage, buyer demand, contractor capacity, payable enquiries, revenue, payment activation or outbound.
- See `INTELLIGENCE_INTEGRATION_20261021.md` for boundaries and test evidence. This branch is **not deployed publicly**.

## Restored cinematic globe, distinct Storm Hub branding (private candidate)

- The **original cinematic Earth composition** is back, now using locally hosted NASA Blue Marble western-hemisphere imagery, with original deep atmospheric lighting. It is a historical source mosaic, not a live storm, warning boundary or weather product. Original reference: https://science.nasa.gov/resource/blue-marble-2002/
- The product is **deliberately not an Empire AI flagship copy**: the corporate neon-blue/gold/glass-console treatment is replaced on the Storm Hub homepage by charcoal/white editorial typography, safety-yellow ZIP actions and reserved red for alert navigation. Blue is retained in Earth and its atmosphere, not as the universal UI identity.
- Removed the synthetic orbit lines, fake hazard/location pins, telemetry labels, weather side card, numbered benefits ribbon, mock Atlas radar and fake contractor-console checkboxes.
- The Atlas now displays actual source-dated NWS results, with unavailable and zero-result states clearly distinguished.
- Kept user features (ZIP, Predictor, Alerts, Passport, research/recovery) and existing source policy unchanged. No founder-only finance link appears in the public homepage footer.
- Current read-only private comparison: `http://127.0.0.1:3159/`. Browser screenshots checked 1440×950 desktop and 390×844 mobile, without horizontal overflow or client exceptions. 23 Node tests and production build passed. Public deployment is **not** authorized by this private redesign branch.

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
