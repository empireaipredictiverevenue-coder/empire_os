# Empire AI — Deep Public Data Source Sweep and Source-Mining Wave 2

18 October 2026 | Founder directive: meaningful, £0-cost UK + US sources
Branch: `feature/predictive-decision-control-20261018`
Canonical database: EmpireDB (PostgreSQL), **not Supabase**.

## Outcome

- **19 reviewed source opportunities**, not 19 active production streams.
- **4 existing** connectors/data reviews already inside EmpireOS: US NWS,
  NYC DOB NOW permits, Empire-owned Google Search Console and already reviewed
  historical Common Crawl graph.
- **2 new one-shot read-only adapters** implemented and tested: UK Find a
  Tender public OCDS and Environment Agency flood warnings.
- **8 additional adapter candidates** requiring targeted source/contract
  checks before engineering. Other holdings: **2 API-key gated**, **1
  privacy/address-rights hold**, **1 empty source dataset** and **1
  commercially incompatible free hosted tier**.
- No live systemd polling, API spend, production migrations, outbound, lead
  creation, new data lake or financial operation introduced.

## Commercial source priorities

### P1 — Published UK public procurement opportunities

Public source: [Find a Tender](https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages) and
[Contracts Finder](https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Published-Notice-OCDS-Search).

The public OCDS release endpoint supports stage, update-window, limit and
cursor filters; its limit is 1–100. Distinguish this PUBLIC output API from
the Find a Tender authenticated notice SUBMISSION API.

**Why it matters:** an actual published procurement notice is stronger
evidence of organizational purchasing requirements than generic search-result
counts. It still does **not** prove the contract is unawarded, accessible to
Empire AI, paid for, won, within our capacity or a demand for consumer leads.
The notice may be a correction to an existing tender.

The new `uk_public_tender_observer.py`:
- makes at most one 8-second bounded fixed-host request per explicit call,
  using `updatedFrom` for the prior 30 days and `stages=tender`, limit 5;
- validates Cabinet Office publisher, OGL metadata, unique OCDS release IDs,
  tag=tender, status/deadline and CPV classifications;
- maps only narrow CPV codes for roofing, solar, HVAC and dental; unknown
  classes stay unclassified rather than using noisy descriptions;
- sends **no person, email, phone, buyer name, free text, supplier list,
  contract value or private provider payload** into aggregate mining output;
- preserves fingerprints, original OCDS record references and scenario truth
  while keeping buyer acceptance, award, payment and recognised revenue false.

Live bounded pilot on 18 October: 5 releases on 1 limited page, all
source-marked `active`, no matched priority CPV in that 5-record page. The
sample hit the configured page limit; **no complete market counts, number
of truly open contracts or sector market share were established**.

**Next technical step:** source-owner-approved, frozen incremental update
window; follow validated `links.next` cursors with a strict page/bandwidth
budget; maintain dedupe by release and OCID; classify official CPV and
submission deadline; return internal analyst findings to the existing Source
Intelligence/Opportunity Factory. Never auto-bid or scrape contacts.

### P1/P2 — Environment Agency public flood warnings

Official [EA live flood-monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference).
Open Government Licence v3 and official attribution required.

The new `ea_flood_source_observer.py`:
- makes at most one fixed-host, bounded public GET, timeout 8 seconds;
- validates publisher, licence, official warning ID, severity and geographic
  source code;
- generates the **existing**
  `real_world_event_intelligence.SourceEvidence` object per event;
- keeps source-message times (which may omit an offset) **uninterpreted**
  instead of inventing UTC event times;
- does not copy descriptions, personal address text or contact details;
- represents observed government warning-source data, NOT independently
  verified physical damage, an impacted roof, insurance claim or buyer need.

Live bounded pilot on 18 October: valid OGL source response, 0 warnings in
the bounded sample. No global "all clear" or independent damage claim is
derived.

**Next technical step:** cross-check original warning identity/geography
with existing Sensor Mesh and current event truth, then route only internal
regional source intelligence; no automatic homeowner targeting or calls.

## Secondary public sources (government/official)

| Source | Evidence usefulness | Readiness/hold |
|---|---|---|
| [OpenFEMA disaster declarations](https://www.fema.gov/about/openfema/data-sets) | US disaster/county declaration history | New adapter research, not address-level damage |
| [US Census Building Permits Survey](https://www.census.gov/construction/bps/index.html) | Monthly construction authorisation by geography | Aggregate trends; no purchaser |
| [USAspending](https://api.usaspending.gov/docs/endpoints) | Actual reported federal award history | New adapter; previous awards not tender leads |
| [EPA ECHO](https://echo.epa.gov/tools/web-services) | US facility environmental observations | Source facility data, not buying intent |
| [UK EA rainfall](https://environment.data.gov.uk/flood-monitoring/doc/rainfall) | Government gauge observations | Sensor Mesh, not damage evidence |
| [Ofgem FIT installations](https://www.ofgem.gov.uk/transparency-document/feed-tariff-installation-report-30-september-2026) | UK solar accreditation geography / historical installed base | Quarterly; reports in multi-part Excel files, not current homeowners |
| [ONS beta API](https://developer.ons.gov.uk/) | UK local economic trends | Open API, data-specific provenance required |
| [EIA API](https://www.eia.gov/opendata/documentation.php) | US solar/energy market fundamentals | Free registration/key required |
| [Companies House](https://developer.company-information.service.gov.uk/get-started) | Company filings and organisational events | API key required; no automatic director personal-data mining |

### Existing authoritative sources to REUSE

- [NWS weather API](https://www.weather.gov/documentation/services-web-api):
  already represented by EmpireOS Storm Predictor / CAP agent / Storm Source.
  An identifiable User-Agent is mandatory; rate limits exist. No second storm
  crawler or unverified property damage inference.
- [NYC DOB NOW / NYC Open Data](https://www.nyc.gov/opendata/get-started/user-guides/open-data-apis):
  already has crash-replay-safe date coverage and a source inbox.
  Reuse that; no duplicate Socrata ingestion.
- Owned Google Search Console: existing authorised site property.
  Its query/result coverage does not represent all market searches or sales.
- Common Crawl: existing historical domain graph; not verified live backlinks
  or consent to send.

### Explicit holds

- [Planning Data planning-application dataset](https://www.planning.data.gov.uk/dataset/planning-application):
  official catalogue shows zero records and zero source providers as of
  this sweep. Not an active national application lead feed.
- [EPC API](https://epc-preview.opendatacommunities.org/docs/api):
  includes personal data and Royal Mail-address licensing restrictions.
  Hold household-address/contact use and commercial productization pending
  field-by-field rights and data-minimisation checks. Regional aggregate
  analysis may be a narrower future candidate.
- [Open-Meteo hosted free tier](https://open-meteo.com/en/terms):
  free endpoint is explicitly non-commercial. Empire AI is commercial; do
  not silently use the free hosted service. Existing official NWS and EA
  streams are stronger £0-first options, and any future commercial licence
  would require separate funding/approval.

## Source selection engineering added

- `empire_os/public_source_sweep.py`: versioned, deterministic source
  catalogue, rights/auth/status distinctions, source priorities and
  two-source internal team-review packets. The catalogue does not poll.
- `empire_os/uk_public_tender_observer.py`: single-shot bounded public UK
  OCDS parser and CPV classification; no saved source data or contacts.
- `empire_os/ea_flood_source_observer.py`: official flood record parser
  producing established SourceEvidence truth contract.
- `scripts/review_public_source_sweep_20261018.py`: safe manual CLI with
  no network by default; explicit one-shot probe flags.
- The existing `revenue_stream_mining` Founder Console API and React view
  now display the deeper catalogue status and new-source priorities, while
  the four current source adapters and five existing department lanes remain
  unchanged. No production Founder Console deployment yet.
- Tests verify authenticity, bounds, duplicates, tenant/customer data
  exclusion, public source evidence, £0 work queue reviews and tamper holds.

## Operator commands

Catalogue only; no network:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_public_source_sweep_20261018 --full-metadata
```

Two bounded, explicitly requested live-source snapshots:

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_public_source_sweep_20261018 \
  --probe-ea-flood --probe-uk-tenders
```

Route **two zero-external-spend internal team source review tasks** to the
existing ASTRA `DepartmentWorkQueue`, idempotent fingerprints, no automation:

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_public_source_sweep_20261018 \
  --enqueue-internal-reviews
```

**Execution evidence (18 Oct 2026):** two new existing-queue research tasks
were accepted, one Business Development review of UK procurement source
quality and one Market Intelligence review of EA environmental source
integration. A second identical handoff returned 0 new, 2 duplicates. Both
were verified in the canonical department `ready` directory with
`authority=observe`, requested external cost 0, and no paid source or
outbound activation. **Tasks are queued, not completed analyst findings.**

Running any of the above **does not activate a continuously polling source
pipeline or write into EmpireDB**. Source activation and schedule changes
must be coordinated with existing Source Intelligence/Sensor Mesh owners;
otherwise duplicate jobs, incomplete coverage or bad evidence could corrupt
our economic learning signals.

## Exit criterion: predictive revenue, not big-data vanity

A source is promoted toward Predictive Revenue only if original evidence,
time, licence, cost, regional relevance and repeatability are understood;
legal/data-rights restrictions are honoured; commercial demand comes from
actual buyer or procurement facts; and downstream outcomes can later be
matched to original predictions and measured in Economic Memory.

Counts of downloaded records, region-wide permits, clicks or environmental
warnings are **not** realised revenue. No model weights or external financial
authority are changed by this work.
