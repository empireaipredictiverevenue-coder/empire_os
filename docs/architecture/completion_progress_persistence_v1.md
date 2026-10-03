# Completion Progress Persistence V1

Architecture delta for the existing whole-business completion programme.

- Owner: execution-plane completion programme; Founder surface is a read-only consumer.
- Purpose: reconcile persisted progress with live Git identity, canonical checklist counts, and execution leases.
- Truth: repository Git state, MASTER_REMAINING_CHECKLIST.md, and execution-plane leases.json; unknown remains unknown.
- Authority: bounded internal write to the completion progress artifact only. No outbound, terms, funds, revenue recognition, migration, restart, or authority expansion.
- Execution: deterministic on-demand reconciliation with atomic replace; no retry loop.
- Failure: fail closed on invalid JSON, Git failure, malformed leases, or malformed progress structure.
- Verification: focused unit tests, compile, diff check, then read-only Founder API verification after bounded reconciliation.
- Commercial fit: prevents stale programme state from misdirecting revenue/completion work; creates no commercial evidence.
- Rollback: restore the prior progress artifact; code changes are isolated to this module, test, and contract.
