# EmpireOS Predictive Revenue — tenant terminal cohort reader

20 October 2026. Existing Canonical EmpireDB source, existing Scientific Research Agent, existing Quant components. This is an actual restricted **SQL SELECT source adapter**, not a new fabricated data supplier, duplicate scientific agent or independent forecast issuer.

## Original owner interfaces reused

- Migration `migrations/empiredb/018_tenant_context_foundation.sql`: authenticated `session_user` tenant mapping via `public.empire_current_tenant_id()`, `empiredb_tenant_reader`, tenant policies on buyers, orders and commercial events.
- Existing original migration `migrations/empiredb/056_verified_order_tenant_reader_select_held.sql`: **not assumed applied**, but prepares `order056_outcomes_tenant_select` and select-only grants for `commercial_outcomes`, BSC payment/escrow evidence. Do not recreate or apply migration 056 from the Predictive feature branch; follow original owner and DBA review.
- Original `commercial_outcomes`, `fulfilment_orders`, `buyers` and `commercial_events` objects; no shadow SQL tables, customer file copies or invented user identity.
- Existing `predictive_tenant_outcome_reader_preflight.py` is updated to target the original `order056_outcomes_tenant_select` policy, not a second non-existent policy. Additional broad SELECT/ALL policies are flagged.

## Build details

`empire_os/predictive_tenant_terminal_cohort_reader.py` implements `read_tenant_terminal_candidates`:

1. Requires a separately provisioned, dedicated DB login and an explicit read-only transaction, sets only the existing `empiredb_tenant_reader` role.
2. Validates canonical EmpireDB, read-only mode, trusted DB `session_user` tenant, safe login and reader role shapes, effective RLS for a non-owner (or FORCE RLS), table SELECT grants and absence of extra broad policies.
3. Reads at most **201 rows** (200 is cap) from the original order/outcome tables, with existing tenant predicate and row-level policies, joined to the restricted revenue-event relation, never using a supplied tenant ID/GUC or self-asserted JSON tenant to grant access.
4. Refuses cross-tenant/missing order lineage, duplicate outcome/order IDs, malformed timestamps, future evidence, synthetic/forecast-derived or unverified evidence, terminal status contradictions, wins without fulfilment and recognized revenue event, and losses with recognized revenue event. Truncation holds all claim of cohort completeness. The policy metadata scan is a preliminary safety check, **not a formal proof of RLS correctness**.
5. Returns only counts and source integrity status. No names, emails, buyer IDs, order IDs, tenant IDs, economic amounts, raw data, private JSON evidence or connection string. No customer labels are copied into Predictive Intelligence or the Scientific Agent.

`scripts/review_predictive_tenant_terminal_cohort_20261020.py` is an OBSERVE-only CLI invoked through `empire-predictive-observe tenant-cohort`. It requires the independently provisioned `EMPIREDB_TENANT_OUTCOME_READER_DSN` for a live read; without it the command gives a clear held status. Do not put credentials in shell history, Git, customer files or chat. This work does **not** create the database login, deploy migration 056, alter the production systemd service or write EmpireDB.

## Scope remaining before scientific learning and paid customers

- DBA must review original migration 056, current deployment status and effective tenant RLS for the restricted non-owner reader (or FORCE RLS), and provision a dedicated least-privilege tenant-bound login.
- Original CRM/Finance source owner must issue genuine independently attested terminal feedback with verified customer/order/product version, payment/fulfilment/settlement/cost evidence, and event availability time. The source reader's outcome count, `co.evidence->>'verified'` and existence of a revenue event do **not** substitute for independent attestation.
- Original Quant registry must prove frozen conversion forecasts registered *before* future outcomes; the existing `recognized_revenue_cents` registry rows are not conversion-probability forecasts.
- Only separately authenticated packets can enter the existing Scientific Research Agent's >=20 past outcome/12 prospective holdout Brier calibration. The reader intentionally exports zero training records and cannot authorize customer forecasts.
- Production source remains at its original owner path and the current observer is independent. No live sales, outbound, payment or model changes are implied by a passing reader test.

Testing: Python synthetic transports exercise the bounded SQL contract, source secrecy, cross-tenant mismatches, duplicate order/outcome cases, missing RLS, broader policy grants, bad roles, malformed timestamps and no-credential paths. Additionally `scripts/test_predictive_tenant_terminal_cohort_pg18_ephemeral.sh` was **executed successfully under `pg_virtualenv -v 18`** on 20 October: it reused the original 056 schema fixture and migration, augmented only that disposable fixture with product/outcome/revenue event columns, then called the actual psycopg SQL reader under two separate authenticated logins. Each tenant saw only its respective candidate (one loss, one win), and an inactive tenant binding failed closed. A PostgreSQL cluster encoding discrepancy was found and fixed by setting a read-only transaction-local UTF8 client encoding before checking trusted session metadata. The disposable cluster was dropped. **The live production database, original deployed 056 state, customer data and production systemd remain unverified/unchanged.**
