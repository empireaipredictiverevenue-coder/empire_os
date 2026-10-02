# Revenue Completion TAM Truth Reconciliation V1

Status: architecture delta / bounded corrective maintenance

## Diagram

TAM coder-plan history -> Revenue Completion Supervisor <- canonical TAM runtime snapshot
                                      |
                                      v
                         observe-only blocker classification

## Contract

Purpose: stop a terminal planning-worker failure from being interpreted as a missing TAM capability after the canonical TAM implementation exists.

Canonical placement: revenue_completion_supervisor; TAM implementation remains owned by tam_market_intelligence, tam_market_runtime, and opportunity_radar.

Truth: planner jobs are execution-history evidence only. runtime/tam_market_intelligence/latest.json is the canonical runtime snapshot. Missing snapshot/evidence remains UNKNOWN/unavailable and must never become inferred TAM.

Authority: OBSERVE only. No DB mutation, outbound, terms, payment, revenue recognition, service restart, migration, or authority expansion.

Execution: the existing scheduled supervisor reads local runtime artifacts. No new worker, queue, retry loop, or external dependency.

Failure behavior: if canonical TAM runtime evidence is unavailable, emit tam_runtime_evidence_unavailable; retain planner failure as diagnostic history but do not claim the product capability is missing.

Verification: focused supervisor + TAM + Opportunity Radar tests, compile, scoped diff-check, then live supervisor timer output. Deployment/restart is not required because the timer launches a fresh process each run from the working tree; live verification must observe the next natural timer run.

Commercial fit: improves completion truth and prevents duplicate engineering. It creates no commercial evidence and no revenue claim.
