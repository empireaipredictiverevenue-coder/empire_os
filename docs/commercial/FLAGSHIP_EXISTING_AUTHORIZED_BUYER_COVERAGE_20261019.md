# Empire AI flagship — Existing-authority buyer market coverage

19 October 2026 | Owner branch feature/predictive-decision-control-20261018

## Commercial gap and the verified production identity boundary

The previous feature-branch customer/buyer evidence reviewer could not query
EmpireDB using the `ubuntu` development actor; it returned
`DataGatewayUnavailable`. This is NOT evidence that the canonical buyer
database is down or that the target market has no buyers.

Read-only service discovery on the 19 October production host confirms:

- Existing `empire-buyer-capacity-readiness.service` already runs as
  `root` with its protected EmpireDB env files and last completed
  successfully at 10:39 UTC; its timer is active.
- The protected `/etc/empire_os.env` is permission 0600 owned by root.
  No credentials, DSNs or tokens were printed or changed.
- Latest **existing successful capacity projection** reports:
  `buyers_seen=1057`, `market_defined=107`, `reviewed=1`,
  `terms_verified=0`, `capacity_verified=0`,
  `delivery_verified=0`, `fully_activated=0`.
- Thus **950 records do not have both required market fields populated**.
  That is missing source coverage, NOT 950 extra leads or evidence that
  these records are relevant to any target region.
- A Little Rock, AR roofing market-research candidate was selected by
  the existing Opportunity Factory scientific pathway, but exact-market
  buyer count remains UNKNOWN until the authorised worker performs the
  new projection. We DO NOT invent a zero, a successful buyer match,
  a buying intent or a signed commercial agreement.

## Implementation: no new DB role, query or infrastructure

This patch augments the existing root-owned
`scripts/build_buyer_capacity_readiness.py` feature-branch source,
immediately after its **existing single canonical buyer projection read**.

- `empire_os/flagship_buyer_market_projection.py`: runs the already
  implemented first-party evidence-review and exact niche+metro comparison
  against the *same in-memory buyer records*; does NOT query EmpireDB.
- Outputs only an opaque hashed opportunity reference, source status,
  range-based market overlap (ZERO, ONE_TO_FOUR, FIVE_TO_NINETEEN,
  TWENTY_PLUS, UNKNOWN), completeness flags and precise next internal
  evidence action. Names, raw IDs, contacts, exact small counts, email,
  market metro and specific phone/webhook URLs are NEVER persisted.
- A zero overlap is claimed only if the whole previously fetched buyer
  projection is bounded/complete, every record's market fields are
  usable, and the global view has no tenant-scoped exclusions.
  A partial subset can establish a **lower bound on observed overlaps**
  but cannot prove market absence. With no validated matches and any
  missing attributes, the market count is UNKNOWN.
- Source stale, altered, future/unknown authority, unsupported market
  keys, malformed buys, projection truncation, unknown tenant scope and
  invalid hashes all fail closed. The authorised worker still produces
  its original buyer capacity snapshot if the optional flagship analysis
  cannot complete.
- `review_authorized_market_coverage_snapshot()` reads and revalidates
  ONLY the existing safe snapshot in the **Founder Decision Control**.
  It never queries the DB, refuses data older than six hours, enforces
  fixed status/action enums and rejects impossible ZERO/UNKNOWN
  contradictions or any private data injection.
- Existing Founder Console private preview can display only the source
  status, evidence range, market attribute completeness and the next
  internal action. It does not expose a buyer list, price, contract,
  delivery channel or model outputs.
- No outreach, CRM mutation, extra server, payment, activation,
  model weight changes or database migration.

### Scope: product value, not just infrastructure

Before deployment, the flagship only knew "11 Opportunity Factory
candidates, 0 Quant packets" and an unauthorized buyer count query returned
UNKNOWN. After coordinating the existing buyer-worker and Founder Console
code, EmpireOS can discover whether the **authorised data we already have**
contains an exact-sector/market buyer *record*, or whether niche/metro
completeness is the first actionable data-quality barrier.

It remains a finder of unverified buyer records, not actual buying intent.
Business Development must obtain the original first-party inbound brief,
confirm the same buyer's specific product, market, postcode eligibility,
price, active purchasing capacity and fulfilment before Quant Brain can
accept any commercial input.

## Integration verification (feature branch)

- Unit regression uses only synthetic buyer rows and canonical four-source
  fixture snapshots; test asserts no second buyer-repository call.
- Tested case buckets: confirmed same market; complete true zero;
  incomplete attributes → UNKNOWN not zero; known overlap with incomplete
  attributes → partial lower bound; tenant-scoped hold; untrusted source
  and truncated buyer inventory.
- Tested existing root-owned script in an isolated temporary directory
  with an injected synthetic database-return value. It used one existing
  buyer projection read per explicit run and stored no PII.
- Founder readback tests reject forged zero claims, stale source
  timestamps, arbitrary opaque IDs and unexpected fields.

No `sudo` credential elevation, production root-worker invocation,
production timer start, production snapshot overwrite, CRM write or
buyer identity export occurred. The owner of
`empire-buyer-capacity-readiness.service` must coordinate rollout.

## Commands for the owners

Source branch:
`/home/ubuntu/empire_agents/predictive_decision_control_20261018`

Preflight regression:
```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_flagship_buyer_market_projection.py \
  tests/test_buyer_capacity_readiness.py \
  tests/test_revenue_market_buyer_linkage.py \
  tests/test_founder_dashboard.py
```

Next coordinated release:
1. Owner merges the safe projection module and **existing** buyer-capacity
   worker script; do not substitute a new DB principal or restart another
   agent's CRM worker.
2. Re-run the existing service once through its established, approved
   systemd unit, inspect the new aggregate snapshot shape, origin, freshness
   and original old fields.
3. Owner merges the Founder Decision Control and UI changes as a matching
   release. Confirm signed founder access and no private buyer payload.
4. If market coverage is incomplete (the prior snapshot was 107/1057),
   prioritise lawful niche+metro enrichment and organisation identity
   proof within the authorised business development workflow.
5. Link a genuine first-party buyer reply, signed terms and capacity proof
   to ONE exact Opportunity Factory candidate. Quant Brain may only then
   use source-evidenced economics and prospective/outcome calibration.
