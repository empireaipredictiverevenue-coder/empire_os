# Predictive registry and original commercial outcomes — read-only owner check

21 October 2026. Existing Predictive owner; EmpireDB PostgreSQL, NOT Supabase.

The existing protected tenant login and `empiredb_tenant_reader` role have passed original EmpireDB read-only and RLS policy inspection for buyers, orders, commercial events and outcomes. That **does not** prove that this role may SELECT from the distinct `public.predictive_forecasts` registry.

`empire_os/predictive_existing_tenant_registry_receipts.py` adds a read-only original registry check:
- Uses only the existing root-protected tenant DSN and RLS-derived tenant ID; checks session database, transaction, login and restricted role identity, the exact registry table's SELECT/UPDATE/DELETE grants, and its restricted SELECT policy **before** reading any candidate rows.
- Queries `public.predictive_forecasts` only if the original tenant role already has the necessary constrained SELECT rights and an independently inspected scoped RLS policy.
- Reads at most 101 original records to prevent reporting a truncated 100-row sample as a complete registry; validates tenant scope, metric, UUIDs, amounts, duplicate keys and timestamps.
- Reports **aggregate counts only**. No original ids, forecasts, tenant names, customers or credentials leave the source review.
- Treats a stored row as a *candidate registry observation*, not as proof of an immutable, prospectively frozen signed forecast, a matched outcome, settlement, calibrated model, or training label.
- Requires no grants, extensions, DDL, login creation, deployment restart, network provider calls, outbound send or payment.

`scripts/run_guarded_predictive_registry_readonly_20261021.sh` accepts `--check` to check an exact Git commit without reading the database, and `--run-read-only` for the owner-approved source inspection. The latter performs a bounded `git archive` of only four required source files, verifies per-file object hashes, pins them read-only under root-owned `/opt/empire/predictive_registry_readonly_<commit prefix>`, and executes the review via Python `-P` in an isolated environment with the existing root-owned `PGPASSFILE`. No mutable checkout code is imported with privileged credentials.

The **separate** existing command `/home/ubuntu/.local/bin/empire-predictive-founder-reader both` checks tenant order/outcome source policy and reads bounded original terminal candidates. Even a matching pair of candidate counts does not mean revenue or forecast accuracy: proof requires a frozen registry receipt predating the independently verified, matched original financial outcome. Maintain the Cloud customer-forecast hold until those sources meet admission standards.

If registry access is missing, report `EXISTING_READER_REGISTRY_NOT_ADMITTED` or `HELD_ORIGINAL_REGISTRY_ACCESS_UNVERIFIED` and stop: do **not** bypass tenant isolation or grant the existing reader broader privileges.
