# Empire AI flagship — buyer niche and service-area evidence recovery

19 October 2026 | Owner: `feature/predictive-decision-control-20261018`

## Why this is the next commercial step

The already running authorised `empire-buyer-capacity-readiness.service`
last completed on 19 October and its latest legitimate aggregate reports:

- 1,057 observed buyer rows, **107** with nonempty niche and metro labels.
- 950 rows lack at least one field (source count; NOT 950 new leads).
- One buyer reviewed, zero verified commercial terms, capacity, delivery
  or fully activated buyers.
- A source-known market alone is NOT buyer demand, contact consent,
  binding terms or a quote.

The existing `buyer_acquisition_team`, `buyer_deferred_enrichment` and
`buyer_recovery_action_desk` already own follow-on first-party company
research. We must route the known source gaps to them—not install another
agent, scrape 950 contacts blindly or guess markets from company names.

## What was implemented

`empire_os/flagship_buyer_enrichment_triage.py` is an offline pure reader
over exactly the existing `BuyerAllocationDataRepository.buyer_page` rows
loaded by the root-owned buyer-capacity service.

For each record, assign exactly one deterministic source state:

1. `TENANT_SCOPE_HELD`: not eligible for founder-global enrichment.
2. `INVALID_MARKET_FIELD_FORMAT`: source niche or territory cannot be used
   by the existing **strict exact-match** market adapter. This may reflect
   ordinary business labels containing spaces, so it is a source
   *normalisation/review need*, NOT proof that the original label is wrong.
3. `BOTH_MARKET_FIELDS_MISSING`: requires verified niche and service area.
4. `NICHE_ONLY_MISSING`: requires first-party buyer vertical confirmation.
5. `METRO_ONLY_MISSING`: requires first-party service-area confirmation.
6. `BOTH_MARKET_FIELDS_PRESENT`: only confirms that two source strings
   pass the narrow market matching contract, not buying intent.

The prioritized tasks reuse `buyer_qualifier`,
`buyer_conversation_intake` and `business_development` roles in the
existing Buyer Acquisition Team. No automatic queue submissions, no
background agents and no vendor AI calls. Input is not modified.

Aggregate family labels reuse existing `niche_taxonomy.niche_family`
to avoid creating another vertical registry. Solar, roofing, HVAC, legal,
insurance, restoration, plumbing and medical claims are explicit
research cohorts only; other verticals remain in the total source
inventory and cannot be silently reclassified as those categories.

Output is intentionally bounded and privacy-preserving:
- Exact global total/completeness numbers match the existing authorised
  snapshot; narrow subgroups use ZERO, ONE_TO_FOUR,
  FIVE_TO_NINETEEN or TWENTY_PLUS to suppress rare raw counts.
- No individual buyer IDs, names, contacts, website, phone, contracts,
  unit prices, tenant IDs, metro values or raw customer records.
- False flags for buying intent, terms, model/forecast promotion, outbound,
  CRM mutations, customer verification, or payments.
- If the optional triage fails, the existing buyer-capacity worker still
  completes with a safe `BUYER_MARKET_ENRICHMENT_HELD` result.

The existing worker script
`scripts/build_buyer_capacity_readiness.py` calls both the previous
flagship market-overlap adapter and this triage over the **same in-memory
canonical buyer data**; tests assert one DB read per worker invocation.

`review_enrichment_triage_snapshot` validates the existing root-worker
snapshot schema, 6-hour freshness, aggregate arithmetic, exact fixed
action/owner taxonomy, bounded subgroups, unsafe free-form text and
absence of authority before the existing Founder Decision Control exposes
anything to the Founder Console. This is a reproducible read-back
contract, not a cryptographically signed upstream source attestation.

The existing private Founder Console view shows the observed completeness
numbers and up to four priority workloads, including the owning team and
the next evidence action. It does **not** activate any research itself.

## Exact boundaries and next release

This code is NOT merged/deployed. The live canonical buyer-read service,
CRM pilot, source data, Database roles, payment gates and website are all
unchanged. The feature-branch tests use only synthetic isolated buyer rows
and actual existing function contracts.

Coordinated ownership sequence:

1. Buyer-capacity service owner merges the additive adapter, tests and
   worker-script change. Review the existing customer/tenant information
   policy and retain the *root-owned established* EmpireDB reader.
2. Confirm that original capacity fields/counts are unchanged, new
   aggregate contains no raw buyer data, and known market source
   incompleteness is classified rather than fabricated.
3. Founder Console owner merges matching read-only API/UI types and
   verifies founder signed access and mobile formatting.
4. Buyer Acquisition and CRM agents review the bounded high-priority
   buckets against first-party company evidence. Attribute changes to
   canonical records need independent evidence, authority, provenance
   and explicit separate production approval; no auto updates here.
5. Only then verify **one** actual buyer organisation, original buying
   brief, target product/territory, agreed price, delivery acceptance and
   capacity. Send that verified packet to the existing Quant Brain /
   Predictive Revenue product value loop. Calibration requires later
   verified terminal outcomes, never a market completeness percentage.

## Test and reproducibility

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_flagship_buyer_enrichment_triage.py \
  tests/test_flagship_buyer_market_projection.py \
  tests/test_buyer_capacity_readiness.py \
  tests/test_founder_dashboard.py

cd apps/search-command-centre
./node_modules/.bin/tsc --noEmit -p tsconfig.json
./node_modules/.bin/eslint src/app/founder/page.tsx src/lib/founder-api.ts
```

All operations remain free, read-only to production, and no new outbound,
automated enrichment, payment, CRM write or data store is permitted.


## Canonical tenant-scope hardening discovered during audit

The existing `BuyerAllocationDataRepository.BUYER_COLUMNS` did not
project **`org_id`**, although `public.buyers.org_id` is the genuine
tenant ownership field in the canonical EmpireDB schema
(`migrations/empiredb/000_empiredb_canonical_base.sql`), and the
existing tenant RLS policy explicitly binds readers to that column
(`migrations/empiredb/018_tenant_context_foundation.sql`).

This patch adds **`org_id` to the existing query's selected columns**.
It does NOT add an additional SQL query, DB principal, migration,
tenant grant or write. The actor must already have its legitimate
read privileges to run the same query.

- If `org_id` is absent from any projected buyer record, both
  flagship exact-match coverage and enrichment reviews HOLD;
  absence cannot silently become globally accessible buyer data.
- Records with non-NULL `org_id` are tenant-scoped and excluded from
  founder-global market overlaps and vertical-family classification.
- NULL ownership is not a verified contract, organisation linkage
  or authorisation to sell a buyer's capacity.
- Buyer-specific authenticated CRM views remain the authority for
  tenant evidence. A global operations summary cannot substitute.
- Synthetic regression verifies missing ownership is held without
  leaking a buyer, and a scoped record is never classified as an
  unowned globally available buyer.

Because this changes the canonical buyer reader's selected columns,
the **owner must specifically approve and readback-test that additive
projection change** in the coordinated release. No live query was run
against production under a privileged account in this feature wave.
