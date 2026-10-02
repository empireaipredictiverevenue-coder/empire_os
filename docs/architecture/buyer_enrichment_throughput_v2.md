# Buyer Enrichment Throughput V2

## Diagram

Active buyer backlog -> bounded claim -> 8 parallel enrichment lanes -> evidence gate -> review materializer -> founder-gated outbound

## Contract

Purpose: reduce time-to-review for the active buyer backlog without weakening identity, evidence, commercial, suppression, or outbound gates.

Placement: existing deferred buyer enrichment runner and its existing systemd service only. No new queue, worker family, data store, or authority surface.

Throughput bound: maximum 48 candidates per service cycle and maximum 8 concurrent lanes. Existing per-candidate network budgets and hard probe/identity timeouts remain unchanged.

Safety: enrichment remains internal-only. live_calls_placed stays zero, execution_allowed stays false, and downstream outbound remains founder-governed. Failed or incomplete evidence is deferred, never promoted by inference.

Resources: production host currently exposes 8 CPUs and sufficient available memory; lane count is capped at CPU count rather than made unbounded.

Verification: focused runtime tests, related buyer enrichment tests, compile, diff-check, then install only the matching systemd unit and verify a bounded live cycle. No database migration or outbound action.
