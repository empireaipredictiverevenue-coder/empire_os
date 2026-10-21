# Predictive Revenue — reuse original founder tenant reader, no new login

21 October 2026. Owner-scoped read-only operator integration.

The missing `EMPIREDB_TENANT_OUTCOME_READER_DSN` warning in the ordinary unprivileged `ubuntu` shell was an environment integration gap, not evidence that EmpireDB lacked a tenant reader. The original DB/order owner had already provisioned the one founder-tenant login and SQL 056 policies. Authoritative original-owner evidence: `/srv/empire_os/docs/commercial/FOUNDER_SINGLE_ORDER_READER_PROVISIONED_20261020.md`.

**Exact existing identity reused:** `empire_verified_order_tenant_login`, member of existing NOLOGIN `empiredb_tenant_reader`, bound by `session_user` to the previously authenticated founder tenant. SCRAM password is stored only in root-protected `/etc/empire/verified-order-reader/reader.pgpass`. Never copy, change permissions, print or import it into a normal user process.

## Installed operator bridge

- Repo: `scripts/run_predictive_existing_founder_tenant_reader_20261021.sh`
- Installed: `/home/ubuntu/.local/bin/empire-predictive-founder-reader` (mode 0750)
- Existing OBSERVE launcher: `/home/ubuntu/.local/bin/empire-predictive-observe` now delegates only `tenant-evidence` and `tenant-cohort` to that operator bridge; the other profiles continue using immutable release `predictive_observe_261d07fe9b00`.
- Previous launcher: `/home/ubuntu/.local/bin/empire-predictive-observe.rollback-261d07fe9-rootreader` (operator rollback).

The wrapper verifies all pinned OBSERVE release checksums before invoking a fixed read-only Python module with `sudo -n /usr/bin/env -i`, local loopback DSN, exact approved login name, protected `PGPASSFILE` location and pinned `PYTHONPATH`. No password literal, sudo interactive prompt, postgres/app superuser fallback, customer ID, role grant, migration or database write. Sensitive connection details and tenant identifiers are not emitted by the underlying reviewing modules.

## Operator acceptance

From the original founder's authorized Ubuntu SSH shell:

```bash
empire-predictive-founder-reader --check
empire-predictive-observe tenant-evidence
empire-predictive-observe tenant-cohort
```

Only the first checksum-only command was actually executed successfully by remote agent. The remote desktop command policy blocks `sudo`, so its real root-only SCRAM connection **has not been executed by this agent**. A successful owner execution must return authentic JSON from both modules. If the result says `HELD_TENANT_OUTCOME_READER_POLICY_UNVERIFIED` or `HELD_ORIGINAL_TENANT_TERMINAL_COHORT_UNVERIFIED`, retain holds and investigate server DB/RLS; do not mark it fixed merely because the environment variable was supplied. A zero-candidate result is not a paid order and does not authorize scientific learning.

Mocked no-root tests exercise the sudo argv, module allowlist, normal launcher routing, password non-disclosure and no fallback. Root-only file must remain inaccessible to the ordinary `ubuntu` process.

## Scope

This integration resolves credential reuse without provisioning duplicate accounts. Production Predictive Intelligence writer, external marketing, money movement, original Finance/CRM attestation and immutable pre-outcome forecast registry remain separately gated. An operator credential being available does **not** make product forecasts customer-ready.
