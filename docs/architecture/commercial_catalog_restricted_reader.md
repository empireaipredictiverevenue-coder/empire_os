# Restricted commercial catalog reader correction

Diagram: dedicated login → SET ROLE empire_intelligence_materializer →
public.get_commercial_product_catalog(text,integer) → commercial_products +
commercial_product_versions → observed catalog snapshot → revenue distribution.

Architecture delta (Phase 4 OBSERVE): the commercial catalog component owns this
read boundary. The materializer bootstrap already grants the exact capability;
016 imported the function as INVOKER, which requires forbidden table privileges.
The historical materializer catalog contract explicitly intended a bounded
DEFINER RPC. Restore that boundary without changing the SQL body, result schema,
500-row cap, product evidence, unknown handling, or locked Predictive Revenue formula.

Worker assignment: Codex owns only migration 022, this delta, and its focused test.
Verifier lane: executable PostgreSQL tests in a disposable socket-free cluster,
including negative privilege checks; no production connection.

Retain the existing migration owner empiredb_migrator, subject to fail-closed
checks that it is NOLOGIN, non-superuser, and unreachable by the restricted
materializer and generic app. If production violates these assumptions, stop for
owner review; do not silently alter roles or grant table access. Lock search_path
to empty. Revoke PUBLIC EXECUTE; grant only the existing materializer capability
role, not its NOINHERIT login. Existing named reader grants remain unchanged.
No commercial table grants, terms changes, approval, payment, or revenue authority
are introduced. The transaction refuses pre-existing direct commercial table
privileges for either materializer role (including PUBLIC/inherited privileges).

Execution: explicit, transactional, idempotent migration; no bootstrap rerun,
new scheduler, external side effects, or service restart. SQL errors abort the
transaction. Existing refresh errors remain the observable failure surface.
Rollback: in an approved transaction ALTER FUNCTION
public.get_commercial_product_catalog(text,integer) SECURITY INVOKER; this restores
the restricted-reader failure. Never roll back by granting tables or PUBLIC access.

Promotion checklist: local tests and static checks recorded in task output;
production apply, restricted-login refresh, canonical snapshot inspection, and
Founder surface verification remain pending human execution. Engineering proof
is not production completion. Apply 022 explicitly; do not run the held 018.
