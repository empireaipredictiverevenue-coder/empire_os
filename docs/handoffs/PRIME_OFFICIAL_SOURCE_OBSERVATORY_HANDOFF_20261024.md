# EmpireOS Predictive Cloud / PRIME — original source observatory integration

Date: 2026-10-24.
Branch: feature/prime-official-source-observatory-20261024.
Parent: b017fbbdf (existing source-custody and NWS feature).
Owner: existing Predictive Cloud, Source Intelligence and Core Operations.
Mode: OBSERVE. Isolated source integration. No sales or buyer-acquisition work.

## What has been finished

The original feature work now has a three-step testable path:

1. Existing NWS source -> original storm evidence normalization:
   empire_os/nws_official_source_provenance.py
2. Original universal source custody -> source/reference/rights/clock review:
   empire_os/universal_source_custody_review.py
3. PRIME source observatory -> no-economic-authority source summary:
   empire_os/predictive_cloud_official_source_bridge.py

That third step is newly completed here, and passed optionally into the
ORIGINAL empire_os/predictive_revenue_brain_bridge.py, then to the original
read_prime_founder_status() aggregate-only Founder source reader.

No new service, queue, database, pgvector schema, API endpoint, HTTP timer,
GPU, generic storage layer or fake deal simulator was built. No modifications
were made to Sales, Smart CRM, buyer routing, payment or approval governors.

## Source truth and separation

The new summary accepts ONLY the original NWS review and universal custody
schema/version, OBSERVE mode, explicit non-mutation/non-finance flags, bounded
arrays, exact source class, deterministic fingerprints, valid chronological
timestamps and original evidence-hold blockers.

The new observatory returns:
- source_references_reviewed (numeric only if actual review provided; null
  when source was not connected),
- rejected_observations count,
- freshness: UNKNOWN, STALE or RECENT_REVIEW_UNATTESTED,
- transport_observed_reported: source owner's caller-provided state, NOT an
  independently signed network receipt,
- no economic-signal admission, tenant/entity verification, buyer intent,
  proven physical damage, observed commercial opportunity, payments or
  recognized revenue.

A valid NWS reference is *not* automatically appended to Storm Radar,
Economic Signal Fabric, JEV, PRIME Monte Carlo, buyer cohorts, CRM deals or
revenue. Current source-owned official GET was observed in a separate pilot
and returned zero Illinois alerts at that moment. The new read model handles
real source-derived or simulated alert-bearing inputs without treating them
as paying demand.

PRIME's original storm and permit opportunity counts remain untouched.
Any other provider in the research catalogue must go through its OWN
owner-approved official integration and canonical source/tenant controls.
No general raw JSON, personal data, source URL or unverified dollar amount
is added to PRIME.

## Existing Founder surface

The original read_prime_founder_status() now optionally accepts
official_nws_source_review from the trusted original source owner. No
HTTP request parameter or new public endpoint was added; existing GET
/v1/predictive-cloud/prime/status returns NOT_CONNECTED for NWS until
the original owner independently wires an approved source receipt to its
private read boundary. This is intentional: no unverified source-file write
or client-provided source evidence is silently promoted.

Only safe aggregate status/count/freshness keys are rendered. The route
continues to exclude source records, event IDs, company contacts, properties
and explicit tenant IDs.

## Test evidence

```bash
cd /home/ubuntu/empire_worktrees/prime_official_source_observatory_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_predictive_cloud_official_source_bridge.py \
  tests/test_predictive_revenue_brain_bridge.py \
  tests/test_predictive_revenue_prime_status.py \
  tests/test_nws_official_source_provenance.py \
  tests/test_universal_source_custody_review.py \
  tests/test_economic_signal_fabric.py \
  tests/test_predictive_revenue_prime.py \
  tests/test_predictive_cloud_status_api.py \
  tests/test_economic_memory.py
```

Includes full offline fixture chain through original NWS parser, universal
source custody, PRIME brain and Founder source status, malicious promotion
cases (fake revenue, fake rights, fake economic-signal eligibility), staleness,
duplicate evidence and source-absent/not-a-zero cases.

## Next original build boundary

The Core & Data Cloud owners should reconcile original root work, then
review the exact branch before any private release. Only the original
source owner may supply an independently permission-checked source receipt
through its existing trusted read mechanism. The first source-owned
reference and canonical entity+tenant binding remain independent. Real
economic-signal conversion requires an actually evidenced commercial
condition and independently verified downstream outcome, not one weather
warning. Calibration stays under original Predictive Cloud outcome owner.

NO site traffic, outbound, buyer mails, CRM writes, payment movement,
provider provisioning, production release or schema migrations authorized.

Revert: drop this isolated feature commit without running-state cleanup.
Original production remains unchanged.
