# Empire AI — Physical-world knowledge for predictive market intelligence

19 October 2026 | Owner feature branch:
`feature/predictive-decision-control-20261018`

## Mission: where pain meets the physical world

Join geographic market history, town/city/county identity, hazard records,
local climate, housing/construction stock, materials, building regulations,
supply/labour and customer questions into the EXISTING flagship market
knowledge graph. This gives ASTRA evidence-led ideas about where to
investigate, why local problems may occur and which Empire offers can
plausibly help.

THIS IS NOT a property-damage detection system, an insurance loss
adjuster, an underwriting or safety rating, or a buyer database. A
storm near a city, a popular roof material, a flood alert and a public
complaint do not prove any given roof is damaged or anyone wants a quote.

## Implemented and connected

`empire_os/flagship_geo_material_context.py` uses the existing
`geo_registry.acquisition_markets()` (148 market anchors, US, GB and
international) rather than introducing duplicate place identities.

- Market anchor node -> declared country/region geography node. The
  centroid/metro label is not an official polygon or county mapping.
- 11 external research-source REFERENCES, separately declared by
  jurisdiction, coverage class and source use policy; no automatic
  download, scraping, ingestion or reuse licence is inferred.
- 10 installation/material *categories*: asphalt shingle, standing-seam
  metal, clay/concrete tile, natural slate, low-slope membrane, timber
  shingle, underlayment, flashing/gutters, solar PV mounting, and
  insulation/air sealing.
- 17 material concern/hazard topics, including hail, wind, flooding,
  heavy rain, heat, freeze/thaw, roof leaks, coastal corrosion, tornado,
  snow load, wildfire, seismic and structural loading.
- Material-to-concern typed edges `MATERIAL_REQUIRES_CONDITION_ASSESSMENT_FOR`;
  no claim of installation or measured test performance.
- Typed connections back into the existing Knowledge Graph and
  Pain/Solution Engine:
  `INFORMS_MARKET_MATERIAL_RESEARCH` and
  `SUGGESTS_UNVERIFIED_STORM_PAIN_QUESTION`.
  Physical hazard areas are NOT connected to property, contact,
  conversion, CRM record, claims or payment nodes.
- First research checklists for Chicago/Illinois, Dallas/Texas,
  Manchester/England, Miami/Florida and London/England.
  Roof, solar and HVAC question templates cover building era,
  materials, historic weather, valid building code edition,
  warranty/insurer context, labours and supplier availability,
  actual customer need and the relevant original source.
- Context graphs are attached to the existing Founder read-only market
  knowledge projection. The Quant Brain time-safe feature packet
  is built FIRST from the original approved public market graph, so
  generic materials or empty storm datasets do NOT alter conversion
  probability, buyer status or expected revenue.
- The existing private Founder Console gets geographic source count,
  material/hazard coverage, location-specific research checklists and
  explicit missing-history / missing-damage evidence status.

## Verified first read-only technical checkpoint

- 148 unique existing Empire geographic market anchors.
- 11 external physical-world research references.
- 10 material categories and 17 hazard topics.
- **Zero** original storm-history records from these sources imported
  and source authenticated. This wave registers source families and
  builds a typed *staging* adapter.
- No official US county FIPS or UK GSS correspondence loaded between
  market centroids and verified area geometry.
- No live storm hazard polygons, site materials or permit details
  ingested into this graph.
- No actual building damage or buyer intent verified.
- No model weights trained, Quant probability issued, revenue earned
  or customer contacted.

Synthetically injected test rows can pass schema/timestamp/source-kind
checks, and are staged as `STAGED_AREA_EVIDENCE_SOURCE_AUTHENTICITY_NOT_VERIFIED`.
The adapter explicitly sets
`original_official_record_authenticated_by_adapter=False` and
`actual_historical_storm_events_imported=0` even if a staging row
claims it came from NOAA. This prevents test fixtures from becoming
real historical-source claims. No user-supplied boolean is sufficient
to authenticate a provider record.

### Official source candidates and why each matters

1. NOAA NCEI Storm Events Database (US): historical hail, wind,
   tornadoes, significant events. Bulk CSV exists; historical
   completeness and delayed publication need dataset-year versions.
   https://www.ncei.noaa.gov/access/storm-events-database/
2. NOAA NCEI Climate Data (US): time-ordered weather observations,
   not parcel-level hail confirmation.
   https://www.ncei.noaa.gov/cdo-web/
3. FEMA National Risk Index (US): aggregated hazard-risk screening,
   not actual damages, paid claims or a weather forecast.
   https://hazards.fema.gov/nri/
4. US Census TIGER/Line (US): county/place identifier and boundary
   versions, **not** demographic or materials data by itself.
   https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
5. UK ONS Geography: historical/changeable administrative GSS
   identifiers, counties/local authorities and lookups.
   https://www.ons.gov.uk/methodology/geography/geographicalproducts/namescodesandlookups
6. Environment Agency (England ONLY) real-time flood warnings:
   includes warning area IDs and required OGL attribution.
   https://environment.data.gov.uk/flood-monitoring/doc/reference
7. Environment Agency (England ONLY) rainfall: observed rain gauge
   values, station locations intentionally approximate.
   https://environment.data.gov.uk/flood-monitoring/doc/rainfall
8. US Census American Housing Survey: historic housing-stock and
   dwelling-condition survey estimates, not real roof material of a
   known building and NOT a direct county join.
   https://www.census.gov/programs-surveys/ahs/data.html
9. English Housing Survey: sampling/weighted housing condition and
   construction-era estimates for England, not full GB coverage.
   https://www.gov.uk/government/collections/english-housing-survey
10. English Housing Survey LA stock condition modelling: modeled
    area-level stock conditions and damp; not observed parcel defects.
    https://www.gov.uk/government/collections/english-housing-survey-local-authority-stock-condition-modelling
11. IBHS/FORTIFIED material/building-resilience standards: learning
    about roof construction/installation choices, not proof that
    a particular property is protected or certified.
    https://fortifiedhome.org/

Other future source families recommended, not connected or imported:

- Local planning/permits and historic building code amendments, with
  effective dates by jurisdiction, building age and roof replacement.
- Official city/county boundary code history, zoning, development era,
  home retrofits, roof age distributions and public utility
  infrastructure (subject to licensing and privacy).
- Real first-party manufacturer product data: impact test standards,
  safe installation rules, maintenance/warranty exclusions, corrosion,
  fire, thermal and wind performance per exact SKU and code edition.
- Wildfire smoke/fire boundaries, earthquake events, snow/ice,
  extreme heat, drought and floodplain changes as geographically
  typed *different evidence classes*, not one generic 'storm risk'.
- Labour licences, verified contractor/service-area capacity,
  material price history, inflation, lead times, insurance claim
  benchmarks and supply bottlenecks with defensible rights.
- Local economic/demographic context, affordability, business opening/
  closure rates, housing tenure, commercial building types and energy
  use to understand pain and potential financial feasibility.
- Across other verticals: solar array materials and irradiance,
  HVAC climate/load codes, agricultural soil/drought, medical
  facility standards, legal exposure and insured mass-tort geography.
  These require distinct scientific ontologies and should not be
  inferred from the roofing source set.

## Critical scientific constraints before predictive use

1. Verify the original downloaded/signed/source-retained provider
   record, hash, source publishing date, retrieval date, version,
   programme terms and permitted reuse BEFORE admitting an
   observed claim. A SHA supplied in JSON alone is not authentication.
2. Resolve the admin-area FIPS/GSS into a versioned real county/LAD
   polygon, then spatially join with separately authorised coordinates
   only if precision and geometry are sufficient. Never guess a
   county from a city label, centroid, postcode or nearby county.
3. Distinguish a recorded historical event from a *forecast*, a
   warning/alert, a climatological average and a static risk index.
   Recorded events must finish before their published record is known.
4. A historical city/counties storm aggregate is NOT site damage,
   insurance validity, claim acceptance or verified buyer need.
   Inspection, owner authorisation and commercial evidence remain
   separate original sources.
5. Prevent time leakage: only reports actually available BEFORE a
   prospective prediction may be used. Annual historical datasets
   often contain events reported or corrected after event time.
6. Preserve source coverage and denominator for negative evidence;
   missing storm rows are 'unknown dataset coverage', NOT 'zero storms'.
7. Evaluate additional geographic/material features *against*
   prospective verified outcomes out of sample and compare with
   baseline Quant model. No probability or revenue estimate is
   issued by the ontology itself.

## Owner handoff and deployment state

New module:
`empire_os/flagship_geo_material_context.py`

New tests:
`tests/test_flagship_geo_material_context.py`

Changed the already owned decision/read UI only:
- `empire_os/predictive_decision_control.py`
- `apps/search-command-centre/src/lib/founder-api.ts`
- `apps/search-command-centre/src/app/founder/page.tsx`
- `tests/test_founder_dashboard.py`

Feature branch only. No production services, background source
collection, EmpireDB schema/permissions, live outbound or payment
settings changed. The owner of existing `ea_flood_source_observer`,
Storm Intelligence, Source Intelligence and geographic exposure
should coordinate the future real-source adapter rollout rather
than having another agent launch a competing scraper.

**Next revenue-critical task:** import ONE bounded authentic historical
NOAA event-year or EA area-alert record and its OFFICIAL administrative
crosswalk through the existing Source Intelligence custody, then
assemble a geography/material problem diagnosis for the first
authorised buyer's exact market. Only source-evidenced economics and
real fulfilled outcomes can later improve the forecast.
