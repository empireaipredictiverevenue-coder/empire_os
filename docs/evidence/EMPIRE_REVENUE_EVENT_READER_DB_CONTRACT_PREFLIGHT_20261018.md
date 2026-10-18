# Empire AI — original recognised-revenue event reader: database-contract preflight

**18 October 2026 | Existing EmpireDB only | read-only / OBSERVE**

## Finding, not a claim of missing production database objects

The existing `empire_os/predictive_revenue_canonical_reader.py` is present in the current worktree and implements `read_recognized_revenue_event` with an expected `SET LOCAL ROLE empire_predictive_revenue_evidence_reader` and a parameterised call to `public.read_predictive_revenue_event_v1(uuid,text)`.

A bounded check of **repository source files** under `migrations/empiredb/*.sql` found no `CREATE [OR REPLACE] FUNCTION public.read_predictive_revenue_event_v1(...)` declaration. The reader file itself is presently **untracked** and belongs to another agent; it is intentionally unchanged. **Repository inventory does not establish that the function or role is missing from the live database.** Conversely, the local reader's Python code does NOT prove its PostgreSQL role, grant or function exists.

A local ordinary user `ubuntu` attempt to query EmpireDB was denied because the `ubuntu` database role does not exist. Protected PostgreSQL-role inspection through the connected terminal was not authorised. **No data records were read; no credentials, dedicated roles, DDL or payment state were altered.** This is an explicit, evidenced blocker to completing the first original source-event verification.

## Implemented in this release

- `empire_os/finance_event_reader_source_contract.py`: tiny read-only source inventory with a strict `CREATE FUNCTION` definition pattern over bounded local migration files, distinct from runtime SQL proof. Does not falsely turn an available Python file or proposed SQL into a deployed capability.
- `scripts/review_predictive_revenue_reader_source_inventory_readonly.py`: on-demand source inspection requiring `--read-only`. Prints no customer data, source extracts, secret or inferred finance totals.
- `empire_os/enterprise_finance_evidence_readiness.py`: the **existing** finance source read model now carries `single_event_reader_repository_prerequisites` alongside the existing three internal source snapshots and seven independent proof gaps. Existing customer/revenue release flags are unchanged.
- `scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql`: a **transactionally READ ONLY** `pg_catalog` probe. It checks exact role, NOLOGIN/admin/RLS bypass restrictions, expected function signature, STABLE/SECURITY DEFINER/locked search path, migrator ownership, capability-only function EXECUTE (including no PUBLIC execute), presence of three supporting source tables, absence of direct table privileges for the capability, existence of trusted session-bound tenant resolver and a non-privileged dedicated login member with `SET ROLE` ability. It reads **zero financial rows** and runs `ROLLBACK`. It reports `CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN` only for catalogue attributes; actual function implementation still requires independent review.
- `tests/test_predictive_revenue_reader_source_inventory_20261018.py`: tests missing/source-declared migration states, symlinks, no-write behaviour, source-to-finance report connection and static no-DDL/no-data-query SQL contract.

## Actual next DBA evidence (one command, no password sent to ChatGPT)

From the existing EmpireOS server terminal, an authorised PostgreSQL administrator can run **only the bounded catalogue probe**:

```bash
cd /srv/empire_os
sudo -u postgres psql -X -w -At -v ON_ERROR_STOP=1 -d empiredb \
  -f scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql
```

The expected result is **one JSON line** with booleans and a status. It contains no transaction amount, user identity, buyer information or secrets. If the returned status is `HOLD_EVENT_READER_CATALOG_NOT_PROVEN`, inspect exactly the false prerequisite booleans; **do not apply a migration or create a login** without a separate source-schema and security review. If PostgreSQL catalogue access is unavailable, that is `UNKNOWN/UNVERIFIED`, not a confirmed missing object.

If every catalogue prerequisite is present, the *next* (separate) stage is a restricted login and code-level `SECURITY DEFINER` audit, followed by a single actual record/order match for an authenticated tenant **only if an original event and its source access legitimately exist**. Never fabricate a UUID, create a test payment inside production, equate a single event to a complete day, or release client finance data without customer authority.

## Deliberately not done

No second database, customer-data importer, unapproved migration, production query against finance tables, customer/tenant access grant, outreach, payment, account mutation or new scheduler. Existing Revenue Pulse and report HTTP guard remain in their separate read-only operation. This new preflight is the exact next evidence needed before attempting an actual authenticated finance reader query.
