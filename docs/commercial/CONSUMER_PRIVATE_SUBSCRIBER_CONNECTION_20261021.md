# Empire AI — Private subscriber-service connection and sender suppression

**As of 21 October 2026. Scope: staged source and tests; no production service activation.**

## Verified current production baseline

Original founder privileged terminal readback: `CONSUMER_SCHEMA_INSTALLED_READBACK_VERIFIED`, protected `empiredb` five tables/five policies; role `empire_consumer_optin_writer` exists NOLOGIN, and `consumer_service_login_created=false`. Corrected approved schema fingerprint `fe9da8e0a8871e78103941729fb893c891a542286531a283e0d40f2846026cd1`. PgBackRest backup metadata was validated at installation with newest completed backup 18.4 hours old. No independent restore drill was claimed. Global B2B default grants were preserved while only newly created consumer tables were ACL-sealed.

## Added private runtime integration

- `empire_os/consumer_optin_connection_custody.py`: explicitly injected private password-authenticated DSN, fixed database `empiredb`, dedicated LOGIN identity `empire_consumer_optin_login`, local-loopback-only host/canonical PostgreSQL port, unexpected libpq options rejected, strict non-superuser/NOINHERIT/NOBYPASSRLS runtime role checks, restricted `SET LOCAL ROLE empire_consumer_optin_writer` and transaction timeouts, exact five FORCE RLS tables and five original scoped policies, no unrelated `empiredb_app` or `empiredb_readonly` SELECT. Never attempts to connect when `owner_authorized` is false (default). **The code has no built-in credentials, env-secret lookup, service unit or public route.**
- `empire_os/consumer_optin_suppression_reader.py`: an injectable fail-closed subscriber-state check for the Resend confirmation sender, with HMAC-only lookup, exact purpose/tenant/confirmation token state and a current suppression tombstone check at the point of sending. It never performs any database updates or exports raw personal addresses to logs.
- Existing `ConsumerPostgresRepository` and `PrivateConsumerOptinService` now work through this separate identity in a **real disposable PostgreSQL 18 fixture**, rather than only a mock database.

## Real login authentication and lifecycle proof

`pg_virtualenv -v 18 /bin/bash scripts/test_consumer_private_login_pg18_20261021.sh`:

1. Creates a disposable PostgreSQL 18 cluster, reproduces actual historical EmpireDB per-schema default grants, and installs migrations 057 → 059 → 058 with the previously verified atomic installer.
2. Creates a synthetic `empire_consumer_optin_login` with **SCRAM** test password and exactly one role membership (`empire_consumer_optin_writer`, `INHERIT FALSE, SET TRUE`). Test-only credential is not a real service secret.
3. Verifies a logged-in, non-privileged user can set only the expected writer role, access the five RLS tables, and cannot rely on unrelated CRM/default grants. HMAC lookups never appear as raw contact text in SQL arguments.
4. Exercises encrypted synthetic pending signup, provider acceptance using a fake sender, double-opt-in verification, unsubscribe, suppression and re-subscription denial via actual parameterised SQL under that login; **no real email is sent**.
5. Revokes private writer membership and proves a new login cannot assume the writer role. The test cluster and all synthetic subscriber records are destroyed automatically.

**148 selected tests passed** across consumer/private identity/provider/gateway cases (one Starlette/AnyIO upstream deprecation warning), plus real PostgreSQL 18 fixture success. No live production database session, customer records, Resend provider send, marketing activation or new server daemon was made by this release.

## Still required for genuine subscriber service

Do not grant the existing public web user, `empiredb_app`, `empiredb_readonly`, analytics or the CRM pilot any membership in the consumer writer. A DBA/security owner must independently approve and provision:
- A **distinct LOGIN** role `empire_consumer_optin_login`, SCRAM authentication and only one explicit restricted writer membership; no reusable CRM credentials, database owner, superuser, or BYPASSRLS. The deployment requires an independently reviewed host authentication rule restricted to the private service identity.
- A nonprinted, securely created long random password in a protected private secret credential file (not source, CLI argument, generic global `/etc/empiredb.env` or Git), and three **separate** 256-bit HMAC/encryption keys under key rotation and erasure custody. The existing shared Resend key should not simply be exposed to the web process.
- An authenticated private service runtime running under its own system identity, with restricted file access, control-plane rollback, rate limits and original legal/privacy signoffs. No public service binding until test mail and unsubscribe have full observed receipts. Sender must perform original suppression and provider-readback checks.
- Privacy/retention approval of the own-brand homeowner notice, correctly functioning public privacy contact, deletion and unsubscribe handling, and exact content provenance approval for the free guide/preference page. A subscriber is never a third-party lead or a resale authorisation.

**Next release is private identity and original key-custody setup**, which is an additional production permission/secret action. Current implementation is prepared-only and intentionally can't authenticate to production without independently authorised credentials.

All payments, lead resale, marketing email, call attribution, website redesign and unrelated predictive cloud configuration are out of scope.
