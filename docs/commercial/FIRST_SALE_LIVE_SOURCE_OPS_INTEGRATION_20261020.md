# First Sale — live enquiry source and conversion-state Ops integration

Date: 20 October 2026
Worktree: `/home/ubuntu/empire_worktrees/first_sale_live_funnel_observer_20261020`
Branch: `feature/first-sale-live-funnel-observer-20261020`

## The real production finding

The restricted tenant-scoped canonical order reader, founder tenant login and five financial RLS policies are provisioned and proven. The original canonical payment tables hold **zero fulfilment orders, zero payments, zero commercial outcomes and zero settlement evidence**.

The existing first-party sales enquiry/CRM acquisition reader
`scripts/probe_canonical_sales_intake_aggregate_readonly.py`, run in a local privileged READ ONLY transaction, returned **zero first-party commercial enquiries and zero Predictive Revenue enquiries**. No buyer, company or personal information was returned.

The old `runtime/commercial_funnel/latest.json` was generated on 22 September 2026. Attempted use of its preexisting refresh path failed because its database function `public.get_founder_commercial_funnel()` does not exist. The older migration 027 that would install this function references outdated/missing tables in the current canonical database. Therefore **do not apply that obsolete migration or use those historic counts as present-day performance**.

The private localhost checkout returned working GET routes and exactly four catalogue products. Its health permits initial order requests but reports `BSC_CONFIGURED_CHAIN_UNVERIFIED`; that is **not a fresh chain proof or a real buyer payment**.

## Implementation

- `empire_os/first_sale_live_conversion_observer.py`: consumes exactly the **existing** canonical founder-scoped acquisition aggregate and existing localhost checkout `GET /health`. Bounded, schema-checked, count-only output; no per-contact records. The old funnel snapshot is used only to report freshness, not metrics. A current original buyer-enquiry count may become an owner review, **never proof of a genuine buyer order**.
- `scripts/run_ops_control_cycle.py`: includes `first_sale_conversion_readiness` and `health_domains.first_sale_conversion` in the already-running private Founder Ops snapshot. The existing systemd Ops timer provides cadence and durable previous-state memory. No new cron, timer, agent, CRM writer or externally transmitted event.
- Runs the privileged original owner query **only** for the exact canonical `/srv/empire_os` root under root; sandbox tests, other worktrees and unprivileged callers fail closed without querying production. The code reuses the already authorised local original read-only query, not a new customer-access role.
- Change memory compares only canonical enquiry counts, checkout state and stale-source condition against the prior allowlisted snapshot. Unchanged holds suppress duplicate attention. A changed count produces a read-only **existing Sales/CRM owner review instruction**, not an email or task dispatch.
- No personal information, company names, prospect/tenant/order identifiers, emails, offer replies or payment details appear in this projection. Broken source evidence returns unknown, **not invented zero sales**.

## Tests

`tests/test_first_sale_live_conversion_observer.py` contains privacy, stale source, forged count/authority and legitimate owner enquiry transition adversarial tests.
`tests/test_first_sale_ops_integration.py` runs the **actual existing Ops Control main** in a fully offline sandbox and verifies baseline, unchanged, an authentic simulated source-count change, suppression and loss-of-source behaviour. Synthetic test inputs are isolated and do not enter production.

Production read-only preview before release found:

- original first-party commercial enquiries: **0**
- original Predictive Revenue enquiries: **0**
- founder entity-bound first-party sales acquisition rows: **0**
- checkout order creation flags on; chain remains **unverified in checkout health** (the separate real chain canary is independently owned)
- old Founder funnel source: **stale**
- verified first sale, realised revenue and gross profit: **not established by this report**

## Next buyer-revenue work

1. Existing website/commercial acquisition owner validates that the published first-party form points to the live consent-gated `/v1/commercial/interests` or Predictive Revenue intake, and observes a **real prospect-created event** (do NOT POST synthetic lead data to production).
2. Sales/CRM owner verifies the founder tenant/business binding, buyer-initiated consent and genuine request; any follow-up requires original qualified authority.
3. An approved product order from the existing self-serve checkout may create a pending payment request only through its existing BSC chain/terms checks.
4. Canonical execution/finance owner verifies actual USDT payment, settlement, fulfilment and cost evidence before recognised revenue or financial model learning.
5. Keep this observer running within existing Ops Control. It will react when original first-party counts change.

No automatic sends, payments, fund movement, external model training, RLS updates or production transactional writes are performed by this integration.


## Public conversion route canary

The currently deployed commercial page's JavaScript calls
`/v1/checkout/commercial/interests` and
`/v1/checkout/commercial/offers`. Direct local virtual-host GET checks
confirm the offers endpoint returns 200, the POST-only interests endpoint
returns **405 to GET as expected**, and `/commercial`, `/buy` and the
catalogue are readable.

The same Ops observation now checks six specific **GET-only** local
virtual-host paths, with bounded timeouts and exact HTTP/content-type
expectations. A 405 on a POST-only route means only that routing is
present; **it does not prove POST validation, CRM delivery, or purchase**.
No synthetic lead, payment token or order is ever submitted. A routing
change produces an existing website-owner review recommendation in the
private Founder Console without sending a message or creating a task.
