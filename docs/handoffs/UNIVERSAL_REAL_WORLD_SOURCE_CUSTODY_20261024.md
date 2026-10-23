# Universal real-world data blueprint: one original EmpireOS source-custody layer

**2026-10-24**. Feature branch:
`feature/universal-data-custody-review-20261024`
Worktree:
`/home/ubuntu/empire_worktrees/universal_data_custody_review_20261024`
Parent feature commit: `bffdc7e48`. No direct changes to canonical
`/srv/empire_os`. Original Core, Data Cloud, Source Intelligence, Economic
Signal Fabric, Economic Memory, CRM, PRIME and finance owners retain authority.

## Real architecture — preserve existing assets

1. Original provider-specific ingestion/scouts (existing permit, weather,
   CourtListener, Reddit, SEO, source intelligence) own actual fetching,
   credentials, permitted rate limits, consent/rights and suppression.
2. New `empire_os/universal_source_custody_review.py` is a **pure offline
   bounded source-reference contract**, not a separate harvesting engine,
   provider connector, Redis stream, paid subscription or database.
3. Existing `empire_os/source_intelligence_handoff.py` performs original
   departmental next-action review. Existing `empire_os/economic_signal_fabric.py`
   remains the authoritative next-stage gate; canonical entity, immutable
   source provenance, verified tenant binding and observed economic-signal
   truth are independently required. Passing this new structural contract
   **does not** satisfy that economic contract. Do not create buyer/lead
   records automatically.
4. Existing Economic Memory, original Predictive Revenue Formula and PRIME
   Monte Carlo are kept; there is no new generic `universal_memory.sql`,
   `universal_data_engine.py` Redis daemon or duplicated simulation engine.
5. Existing EmpireDB/pgBackRest remains primary with no schema/extensions/
   logical replication changes. pgvector availability, model dimensionality,
   vector access scope and RLS are **not independently verified**; do not
   install pgvector or create embeddings now.
6. All paid GPU spending stays **zero until authentic realised revenue**
   plus a separately approved, costed release. The immediately preceding
   feature commit `bffdc7e48` preserves this freeze.

## New code and exact semantics

`review_universal_observations(observations, as_of=...)` checks up to 100
opaque reference records, restricted to eight safe metadata fields. It rejects
raw payloads, email, contact details, tenant claims, artificial revenue,
unknown sources, future/impossible timestamps, unsupported source event kinds,
non-HTTPS or impersonated official host references, and duplicates.
It emits only a stable hashed observation fingerprint, source class, valid
timestamps, source host, access-risk assessment and review blockers.

**Important:** URL/provider metadata is still caller-supplied. No live API,
licence, custody, personal-data status or revenue is independently verified.
Even `rights_claim='licence_claimed'` or an all-green provider record never
grants storage, resale, messaging, tenant ownership or execution authority.

Provider research catalog currently includes:
- GDELT DOC and publisher RSS (news/media).
- SEC EDGAR, Federal Register, CourtListener, PACER (legal).
- Meta Ad Library, Google Ads transparency, Google Trends and Reddit (marketing).
- GitHub release and Hugging Face model references (AI).
- NOAA/NWS and USGS (environment).
- Licensed property data and licensed markets **listed but not enabled**.

Providers are **not** connected or activated by their inclusion here.
Existing original adapters remain the only approved actual collection owners.
No new source polling/crawl is started.

Two pure request builders (they do not send requests):
- `gdelt_doc_query_url("(roofing OR solar)", timespan_hours=3)` uses
  safely encoded query parameters, bounded period and artlist JSON mode.
- `sec_submissions_url("320193")` emits the numeric CIK submissions URL.
  `AAPL` is a **stock ticker, not a CIK**. Verify CIK mapping via the
  actual SEC company identifier mapping rather than padding ticker strings.
  Before connecting SEC, use appropriate declared User-Agent and respect
  SEC fair-access guidance. Never embed an invented identity or send bursts.

## Mathematical corrections / no formula fork

- Pipeline velocity `N * avg deal size * win rate / sales cycle days` is
  an **estimated pipeline throughput proxy**, not settled daily cash
  receipts. Define consistent time units, currencies, cohort and evidence.
- `ARPU * gross margin / churn` assumes stable retention, contribution
  margin and nonzero per-period churn. It is **undiscounted approximated LTV**,
  not NPV. An NPV model needs a discount rate, payment timing and validated
  cohort retention. A zero or unknown churn rate must not mean infinite LTV.
- Bayes' theorem only calibrates decisions if priors and likelihoods come
  from relevant validated cohorts; naming a news signal a 'likelihood'
  is not proof of predictive reliability.
- PRIME's `simulate_pipeline_scenarios` already computes reproducible
  exact-integer-cent P10/P50/P90 hypothetical contract-value distributions.
  Do not add caller-invented random +/-15% pricing jitter, mix currencies,
  call P50 a mathematical mean, or present forecast percentiles as earned
  revenue, accurately calibrated coverage or verified buyer demand.

## Source safety and prioritisation

Prioritize evidence-rich, low-cost official sources with owner permission:
SEC/EDGAR, Federal Register, NOAA, USGS and current original permit sources.
GDELT can surface news coverage, but coverage is not independent confirmation
of truth or the existence of a paying buyer.

Then evaluate CourtListener, Reddit and other permitted sources. PACER can
incur costs; MLS/Redfin/Zillow/property-market datasets, social platform
data, ads transparency, and vendor market feeds require source-specific
rights and/or authenticated API verification. A dashboard displaying an ad
does **not** prove a company's spending amounts or 'CPC +18%'.

Data minimization: do not ingest full court dockets, social account data,
contact details or personal records into universal memory by default.
Evidence rights and individual privacy requirements must be resolved
separately before any expansion or cross-region transfer.

No Solana payout path is reintroduced: existing finance policy is USDT on
BSC with funds movement OFF. This feature has no crypto trading or payment
execution authority.

## Validation and owner release

```bash
cd /home/ubuntu/empire_worktrees/universal_data_custody_review_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_universal_source_custody_review.py \
  tests/test_economic_signal_fabric.py \
  tests/test_predictive_revenue_prime.py \
  tests/test_predictive_revenue_formula.py \
  tests/test_economic_memory.py
```

Required next steps with independent authority before a real provider pilot:
source owner reviews exact data rights and provider API documentation,
chooses one approved low-cost connector (prefer official SEC or NOAA), adds
bounded fetch/HTTP-status/rate-limit/custody receipts under original source
owner, independently verifies consent and allowed uses, then routes
permitted observations through the original Economic Signal Fabric and its
canonical tenant/entity restrictions. Core owner reconciles other concurrent
root branch modifications before merging. No paid source, customer data,
CRM write, outreach, database migration or live publication is authorized.

Rollback: drop feature branch without any running-state cleanup. This is
an isolated, side-effect-free source-review implementation.
