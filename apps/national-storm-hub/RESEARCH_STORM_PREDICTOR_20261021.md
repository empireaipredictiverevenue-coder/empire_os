# National Storm Hub — Research and Storm Predictor Engineering Dossier
**Date:** 21 October 2026
**Owner:** National Storm Hub / Empire AI
**Scope:** U.S. public consumer storm intelligence, official-source weather prediction, preparedness, recovery and adjacent B2B product design.
**Status:** Evidence-backed research + implementation candidate. This does not certify the site, enable a paid lead exchange or authorize weather-based customer outreach.

## Research finding 1: Official-source data has different truth classes

### Current warnings and watches — NWS CAP/API
- [Official NWS Alerts API](https://www.weather.gov/documentation/services-web-alerts)
- State and point lookups supply issued CAP-style warnings, watches and advisories with issuer, area and times.
- **Proven:** NWS issued a message. **Not proven:** that a given household sustained property damage.
- The existing website uses this feed. Every source error must display UNAVAILABLE, not "no alerts".

### Forecast — NWS gridpoints API
- [NWS API documentation](https://www.weather.gov/documentation/services-web-api)
- `/points/{lat},{lon}` resolves a local forecast URL. Office/grid cell information is derived from the point endpoint.
- Forecast periods provide weather descriptions, temperature and wind. Forecasts are **predictions, not observations**.
- The location is an approximate ZIP centroid from Zippopotam. It cannot substitute for a property-specific position.

### Convective risk — NOAA SPC Day 1 categorical outlook
- [NOAA SPC MapServer technical service](https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/SPC_wx_outlks/MapServer)
- [NOAA SPC categorical layer](https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/SPC_wx_outlks/FeatureServer/1)
- The ArcGIS feature service supplies categorical day-1 polygons. Query whether the approximate ZIP centroid intersects an outlook feature.
- **No category returned** means no polygon intersected in this queried layer; it does not mean "storm impossible".
- Categories such as Marginal/Slight/Enhanced/Moderate/High are **not property-level probabilities**; do not attach arbitrary percentages.
- Day 1 data changes several times per day. Store checked-at and available source-issued/valid times, verify mapping and availability.
- This source chiefly covers CONUS. Florida and Texas are first pilots; non-CONUS territories need separate handling.

### Hurricane track and hazards — National Hurricane Center
- [NHC graphical product descriptions](https://www.nhc.noaa.gov/aboutnhcgraphics.shtml)
- [NHC cone limitations](https://www.nhc.noaa.gov/templates/graphics_cone_inc.shtml)
- The cone communicates forecast centre-track uncertainty; dangerous rainfall, wind and storm surge can occur outside it. Never render the cone as an impact boundary.
- Source date and active advisories must accompany any NHC layers. No scraped repackaging as an original proprietary prediction.

### Historical storms — NCEI Storm Events
- [Modern NCEI Storm Events Database](https://www.ncei.noaa.gov/access/storm-events-database/)
- [NOAA 2026 service migration](https://www.nesdis.noaa.gov/news/location-change-storm-events-database)
- Historical event records are compiled after the storm, with reporting delays and limitations; NCEI database now provides search map and bulk datasets.
- Not a live call-injury/property proof service. Do not claim events absent from incomplete history never happened.
- Future: genuine archival Storm Replay with event IDs, reported observations and provenance.

## Research finding 2: Existing EmpireOS predictor is real code, but its contract is commercial and legacy

Verified source paths in production repo:
- `empire_os/storm_predictor.py` has `ROOF_DAMAGING_EVENTS` of Tornado Warning, Severe Thunderstorm Warning, High Wind Warning and Flash Flood Warning; `StormPredictor.scan()` reads NWS active alerts. This classifier is a **warning signal finder**, not a validated 7-day home-damage model.
- `empire_os/storm_service.py` wraps a poller, callback and possible notifications. **Never instantiate from public web routes**.
- `empire_os/storm_intelligence_runtime.py` and `empire_os/storm_opportunity_bridge.py` keep truth class, provenance, commercial readiness and execution gates distinct; do not expose internal buyer/tenant records to anonymous visitors.
- `empire_os/storm_product_integration.py` and associated tests reject false observed claims and avoid treating forecast or an inferred storm signal as paid demand.

Implementation decision: add a standalone, deterministic consumer `lib/predictor.js` mirror of four existing classification labels, validated with unit tests; combine official NWS point forecasts, NWS alerts and SPC day-1 categories. The website code does not import old side-effecting Python or expose CRM/EmpireDB. A separate future internal audited adapter can read only approved summary data from EmpireOS.

## Research finding 3: The competitive gap is the before-to-after relationship

The Weather Channel's 2026 Storm Radar update already advertises AI assistance, advanced radar layers and future radar (see https://weather.com/safety/news/2026-05-02-new-storm-radar-the-weather-channel). Competing on a radar animation alone is unlikely to differentiate.

Strategic point of difference to **test**, not assume:
- Trust/provenance layer: what is a forecast, what is an official warning, what is later observed.
- ZIP-first useful public pages with state-specific safety guidance.
- Free homeowner Storm Passport across seasons.
- Private repair and document history, only with appropriate security and consent.
- Optional, permissioned contractor help and B2B intelligence, separated from household data.
- Accessible, low-bandwidth non-map fallback, freshness and plain-language uncertainty.

## Research finding 4: State hubs require real local depth

- [Texas Division of Emergency Management](https://tdem.texas.gov/) has original preparedness and response sources including flash flood and hail/wind concerns.
- [Florida Division of Emergency Management](https://www.floridadisaster.org/planprepare/) and [NHC](https://www.nhc.noaa.gov/) support hurricane/evacuation content with local decision emphasis.
- [Google doorway policy](https://developers.google.com/search/docs/essentials/spam-policies) cautions against many near-duplicate geographic pages.
- Build locally useful guides, original source tables, distinct hazard patterns, real geographic tools and editorial verification. Never launch 50 generic state pages just for search engines.

## Research finding 5: Privacy, trust and commerce

- [FTC guidance on information minimization](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business)
- Only request ZIP in public preview. Browser-local Passport until a properly designed encrypted first-party account/vault is separately tested.
- For future property documents, determine lawful purpose, consent records, access rights, incident response, retention and deletion/export.
- Local warning signals never transfer to Lead Exchange without separate consumer request and contractual partner capacity.
- Pro subscriptions, state licensing, insurance representation and referral rules require legal/contractual review. No buyer payouts until actual collected funds.

## Next engineering milestones (ranked)
1. **Now:** read-only NWS local forecast + SPC categorical outlook + EmpireOS event classification, with dynamic source state tests.
2. **Now:** detailed sourced research library and real recovery guide; entry points from homepage.
3. **Next:** MapLibre-backed geographic map with official NWS GeoJSON geometries, verified attribution and accessible fallback; don't substitute illustration.
4. **Next:** authentic NCEI storm-history retrieval and reconciliation by event ID, staged behind source freshness checks.
5. **Next:** privacy/legal publishing review; product analytics devoid of personal-data resale; inclusive mobile and keyboard tests.
6. **Later:** EmpireDB Passport authentication and encryption, consented contractor workflows, Pro subscription, independent operational/commercial readiness and case-study metrics.

## Site safety invariants
Forecast != observation; warning != verified damage; SPC category != property insurance loss probability; no source != no risk; legacy commercial score != customer advice; synthetic illustration != real data; internal transfer != third-party revenue.
