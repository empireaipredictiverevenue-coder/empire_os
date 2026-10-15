# EmpireOS Founder Ops — Conversations & Replies evidence gate

**Date:** 15 October 2026. **Integration:** existing Ops Control snapshot.

## Real source truth

- The canonical Conversations & Replies control lane has 5 of 11
  `VERIFIED_RUNTIME` controls. This describes internal control wiring,
  NOT real buyer interest or an authenticated inbound reply.
- Six controls remain unverified: canonical identity, conflict detection,
  entity classification, evidence lineage, outcome linkage, output quality.
- The collector currently reports five admitted conversation candidates,
  zero canonical messages, zero observed inbound reply candidates and zero
  verifiable historical reply joins; its admission stage cannot
  authenticate buyer/tenant identity.
- The read-only reply linkage plan holds original provider thread proof,
  canonical joins, real contact/tenant binding, inbound authentication
  and commercial intent classification pending.
- Existing identity-discovery/gap metadata is dated 7 October and is
  stale under the seven-day evidence freshness limit. Re-running a
  generator without genuinely fresher source evidence does not provide
  real freshness.

## Implementation

`empire_os/conversation_control_operational_truth.py` is a bounded,
read-only reader of six existing JSON snapshots under EmpireOS. It
produces only allowlisted status keys, control names and aggregate counts;
it cannot expose raw email bodies, sender identities, source value
fields or arbitrary source blocker text.

`scripts/run_ops_control_cycle.py` now includes
`conversation_evidence_review` and
`health_domains.conversation_evidence` in the SAME existing
`runtime/ops_control/latest.json` snapshot. The existing
`/v1/founder-ops/status` endpoint can surface it after its normal
Ops Control timer runs. No new backend, workers, agents, timers,
databases or systemd units.

## Governance and next real proofs

No synthetic replies, outcome events, legal distribution permissions,
outbound execution, payment, or customer-ready commercial claim is
created. The report is OBSERVE-only even when internal control rows
are verified.

Next actions should target the original inbound provider event identity,
authoritative message/thread IDs, exact reply-to-intent joins, canonical
tenant/contact binding, suppression/privacy checks and independently
verified genuine outcomes. Until those exist, the six conversation
controls and buyer-intent claims MUST remain on HOLD.
