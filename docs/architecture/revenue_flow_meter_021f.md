# EmpireOS Revenue Flow Meter — 021F

## What it measures
Read-only, aggregate **stage observability** across existing EmpireOS receipts:
1. Buyer Scout discovery/probe, new real first-party claims
2. Exact-domain Scout→Reconciliation same-run handoff
3. Holding-area persistence counts (aggregate, not per-ID lineage)
4. Source-verified purchasing statements and strict first-party contact bindings
5. Canonical prospect + observed first-party identity in the Scout cohort
6. Accumulated holding-area Buyer Review inventory and blocked reason counts
7. Independently generated Astra canonical company bindings
8. Historic cumulative outbound, commercial replies, recognized revenue events
9. Current Revenue Pulse recognized-revenue accounting truth

## Critical accuracy rules
- **No invented funnel conversion rate.** Only Scout→Reconciliation has
  exact-domain and bounded same-run timestamps; this reports *coverage*, not
  commercial conversion. Never divide the 197-record accumulated review queue
  by a ten-record Scout discovery batch.
- An existing commercial funnel snapshot may report a historical outbound
  count, but is **stale** if older than 24 hours. Historic counts go into
  `observed_count`; `current_count` is null until refreshed from restricted
  canonical DB reads by the existing owner. We do NOT trigger that DB read.
- Buyer evidence counts are current only when the evidence quality report
  explicitly names the exact Scout generated_at and passes its own stage
  time-alignment check. Quality values from another run are not reused.
- Missing, corrupt, future-dated or wrong-schema receipts are unknown/unavailable,
  never silently represented as zero. Invalid domain and duplicates disable
  exact-domain coverage.
- A validated first-party statement does not prove a real buyer transaction.
  A named company email does not alone establish the specific decision-maker.
  A queued Astra plan is not executed outreach; internal queue count is not
  a sale or commercial advancement.
- Recognized revenue (GBP pence) uses current Revenue Pulse accounting truth,
  distinct from predictive/forecast revenue and from historic funnel totals.

## Trend history and scheduling
The existing Buyer Review Materializer generates the flow meter **after**
writing its regular governed review and quality receipts. This introduces
no new systemd unit, cron job, timer or automatic external action.
It saves `runtime/buyer_acquisition/flow_meter_latest.json` and a bounded
`flow_meter_history.json` of up to 96 aggregate observations keyed by a
deterministic Scout-run hash. Reprocessing the same run replaces the
existing history sample instead of inflating throughput. History contains
no email, person name, raw URL or prospect ID.

## Inspection without any writes

```bash
cd /srv/empire_os
PYTHONPATH=. ./.venv/bin/python scripts/inspect_revenue_flow.py --repo-root /srv/empire_os
```

A manual `--refresh` produces only local private aggregate JSON files,
without a database read/write, outbound or agent action. Output is
permission 0600 on the server.

## Acceptance / operations
The scorecard's `handoffs` express which transitions are domain-joined
and which lack record-level lineage. `source_health` shows timestamp
and expected schema validity. `blockers` ranks holding-area evidence
failures and reports source freshness issues. Existing commercial funnel
owner must separately refresh its restricted database snapshot for current
outbound and replies; this flow meter will not invent that privilege.

A future governed **event-level causal funnel** requires immutable event IDs
through holding, Buyer Review, outbound, genuine replies, payments and
recognized revenue. Do not claim those conversion rates from aggregate
snapshots. All automation continues to OBSERVE by default.
