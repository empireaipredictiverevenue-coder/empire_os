# EmpireOS Predictive Cloud V4.10 — canonical source-rights inventory (HELD)

Date: 25 October 2026.
Build: one original EmpireOS / PRIME / ASTRA / Predictive Cloud / EmpireDB PostgreSQL / Smart CRM.
Deployment: **research fixture only**. SQL 066 is prepared and NOT authorised for production migration. No new login or financial authority has been created on production.

## What is actually proven

1. `migrations/empiredb/066_predictive_source_rights_inventory_held.sql`: A scoped candidate-review inventory plus an append-only terminal revocation ledger. Both have FORCE RLS and no public table access. The only data-reader interface is the bounded `read_empire_predictive_source_rights_held(uuid,text,text)` function.
2. Dedicated capability: `empire_predictive_rights_reader` is required to be NOLOGIN with no superuser/CREATEDB/BYPASSRLS rights. A separately created `empire_predictive_rights_login` may later inherit EXECUTE only after owner review. Migration 066 creates **neither** a login nor a real source grant and checks the original restricted `empiredb_migrator` owner. A wrong database, missing role, existing schema collision or untrusted `session_user` is rejected.
3. The source can be `PENDING` or `CANDIDATE_REVIEWED`, **never production-verified or admitted** under this schema. A read returns `NO_SOURCE_RIGHTS_HELD`, `PENDING_HELD`, `CANDIDATE_REVIEW_HELD`, `EXPIRED_HELD`, `FUTURE_EVIDENCE_HELD` or `REVOKED_HELD`. All responses return `real_rights_independently_verified=false`, `source_admission_authorized=false`, `execution_authority=none`.
4. Python `EmpireDbHeldSourceRightsReader` uses an owner-supplied, dedicated PG DSN, `SET TRANSACTION READ ONLY`, bounded statement timeout, an exact `session_user` check, tenant/source/purpose parameters, one-row-only checks and strict negative authorisation. It returns `None` if the record is inconsistent or any access fails. No authenticated request may supply its own connection or trusted roots.
5. `scripts/rehearse_predictive_cloud_v410_source_rights_20261025.sh` runs ONLY under disposable `pg_virtualenv` PostgreSQL 18, with ephemeral SCRAM credentials and explicit owner/login/capability roles. The actual SQL function and actual Python reader prove candidate HELD, cross-tenant absence, direct-table SELECT denied, untrusted EXECUTE denied, append-only receipts, expired records HELD, and revocations terminal. Database is deleted after the rehearsal.

## Security and operational meaning

This protects the shape of **future** licensed data ingestion. It is NOT evidence of rights under NOAA/NWS, SEC, GDELT, prediction-market providers, satellite sources, website scraping, Google accounts or buyer data. Merely writing `CANDIDATE_REVIEWED` or attaching a document digest never authenticates a licence. Real source licensing requires independent signed provider custody, permitted-purpose review, obligations (retention, opt-out, redistribution, geography), tenant authority through the already existing CRM041 reader, and owner-audited provenance.

No application route imports V4.10, and V4.9 remains on the original Founder API service until root-owner systemd activation. This is an add-only/prepared database contract; it **must not** be applied to the live EmpireDB merely because fixture tests passed.

Before approving real deployment: review against current EmpireDB schema/ACL and backup, resolve migration ordering and original roles, obtain separate Data Cloud/Security/CRM/EmpireDB owner approvals, configure separately managed restricted credentials and tested rotation/revocation, add production read-only monitoring and fail-closed rollbacks. Real admission and Redis publishing must be a later independently approved release, not inferred from this inventory.

**No paid traffic, emails, trading, mainnet, funds, DB activation or revenue claim.**
