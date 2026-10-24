# Empire AI / original PRIME — authenticated, tenant-scoped notification evidence reader

**Date:** 24 October 2026
**Branch:** `feature/prime-universal-evidence-fusion-20261024`
**Status:** isolated PostgreSQL 18 research fixture ONLY. No production original EmpireDB migration, user consent, device alert, webhook or revenue.

## Original continuation and actual engineering gap closed

Original PRIME/ASTRA notification path on this same branch:
1. Original Voice Lab fictional Kokoro/Whisper spoken timer proved one local-only two-second expiry; no real device.
2. Held EmpireDB 057/058: tenant-linked immutable timer ledger, protected claim/cancel.
3. Held EmpireDB 059: immutable callback acceptance/delivery-reported records, nonce uniqueness and transition rules.
4. Held EmpireDB 060: restricted stored procedure for receipt custody, no public/application production GRANT.
5. Prior fixture introduced a separate SCRAM-authenticated writer login but used a **privileged disposable database administrator** for the Identity/Privacy consent, timer-claim, nonce and provider-acceptance read path.

**This increment replaces all gateway readback queries with a SECOND, independently SCRAM-authenticated, tenant-scoped and read-only fixture identity**, distinct from the writer. It does not create any new production migration or second database.

## Changes and security boundary

`scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh`:
- Continues to refuse original production port 5432 and non-`/tmp/pg_virtualenv.*/data/18/regress` clusters; installs held 057–060 only in a disposable `empire_timer_fixture`.
- Creates `timer_fixture_identity_reader_login`, a **test-only real LOGIN** with its own independent random SCRAM password, NOINHERIT, non-superuser, no RLS bypass, no role administration and no migrator membership.
- Restricts that reader's `pg_hba.conf` authentication to localhost and exactly the temporary fixture database. The writer's password cannot impersonate the reader; other databases are rejected.
- Grants only bounded column-level SELECT permissions on 057 timer requests/events, 059 receipt metadata, and a fictional `fixture_authorised_device` consent table.
- Adds fixture-only `FOR SELECT` forced RLS policies bound to ONE known **fictional tenant**. A separate synthetic tenant is seeded with its own timer, atomic claim, callback receipt and consent. The reader can see its own tenant rows but not the other tenant's request, claim event, receipt or consent.
- Does **not** grant reader UPDATE, DELETE, direct INSERT or any `EXECUTE` authority over the 060 receipt writer.
- Adds `fixture_lock_current_test_consent` **inside the disposable database only**, a narrowly constrained SECURITY DEFINER function that explicitly checks `session_user` and the fixed test tenant, checks fictional active consent and takes a `FOR SHARE` row lock. Its permission is exclusively granted to the test reader. This is necessary because direct `SELECT ... FOR SHARE` requires stronger table permissions that the reader must not have. No analogous production function is installed here.

`scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py`:
- Uses `_actual_fixture_identity_reader()` to establish a separate authenticated SQL session and verify both its login identity and lack of writer/INSERT/UPDATE permissions.
- All five original injected ASTRA authority readers (device/tenant, consent, atomic claim, provider nonce, prior acceptance) now run through the restricted read identity, not a fixture administrator.
- The signature-validated payload is the exclusive source of metadata. In the receipt operation, the reader session locks active fictional consent and retrieves source digest; while its transaction stays open, the separately SCRAM-authenticated **writer** uses only the original 060 function, which delegates order/replay controls to 059.
- Privileged fixture connections remain solely for **test setup, deliberate synthetic revocation/restoration, and test-only readback/count assertions**. No real Identity source is queried.
- The original fake signed ACCEPTED/DELIVERED-REPORTED callbacks persist in order. Same callback replay, forged provider signature, revoked signed consent, revoked fixture consent and competing writer duplicates are refused. Two stored callback rows do not establish real delivery.

## What was exercised against real PostgreSQL

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
pg_virtualenv -t bash scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_prime_signed_gateway_db_bridge_fixture_20261024.py \
  tests/test_prime_timer_pg_restricted_writer_060_20261024.py \
  tests/test_prime_flagship_notification_gateway_shadow.py
```

Observed fixture results:
- `INDEPENDENT_SCRAM_TENANT_SCOPED_READER_AUTHENTICATED=true`
- `INDEPENDENT_READER_TENANT_RLS_AND_NO_WRITES=PASS`
- `REAL_SCRAM_LOGIN_NO_TABLE_PERMISSIONS=true`
- `SCRAM_LOGIN_DIRECT_TABLE_SELECT_DENIED=true`
- `SCRAM_LOGIN_TWO_WORKERS_ONE_CALLBACK=true`
- `SIGNED_GATEWAY_060_RESTRICTED_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0`

Cross-tenant probes showed zero other-tenant request/consent/claim/receipt rows in the reader's actual SQL session. A direct consent UPDATE and execution of the 060 writer by the reader were rejected. The fixture-only consent-lock function refused the other tenant. The temporary PostgreSQL cluster, logins, data and passwords were destroyed.

## Limits and next exact original-owner requirements

1. The fictional fixed-tenant RLS policies and owner-held `SECURITY DEFINER` consent-lock are **disposable fixture design**, not an acceptable canonical multi-tenant Identity schema. Do not copy these permissions into production.
2. Actual Identity/Privacy/Security owners must identify the existing authenticated user/device/tenant sources, consent/revocation ownership, privacy retention and legitimate key custody. A signed fictional consent envelope is not real consent.
3. Actual EmpireDB owner must review 057–060 against the canonical production schema/roles and approve any minimum necessary read/custody privilege with real tenant authority, auditable transition and rollback. None is applied in production.
4. Actual Notification owner must choose ONE approved sandbox provider and verify its real callback signatures, account/sender rights, accepted vs delivered semantics and user consent. No provider was connected.
5. Actual ASTRA dispatcher needs ambiguous-send reconciliation that does not blindly resend a claimed notification and real-device signed evidence before the Founder cockpit can change from NOT_CONNECTED.

The original local speech/timer pilot, tenant-safe timer and callback data controls remain single-system work. No new parallel assistant/database, no production write, no real alert, no realised revenue or independent valuation.

**One EmpireOS. One EmpireDB. One PRIME / ASTRA / Digital Twin / Voice Lab.**

## Final verified acceptance

- **55 focused tests PASSED**, including the disposable PostgreSQL fixture, two independent SCRAM identities, forged/revoked signature and consent cases and the original Founder/API gateway tests. One inherited Starlette/anyio deprecation warning remains.
- **1,259 scoped affected-system tests PASSED** across original Voice Lab, PRIME, Digital Twin, AGI, Founder, CRM/source/Quant and held PostgreSQL migrations 057–060, with the same inherited warning. This is not the full repository gauntlet or production approval.
- Real PostgreSQL 18 cross-tenant assertions included another tenant's actual fixture timer request, DISPATCH_CLAIMED event, consent and callback receipt. The independent reader saw zero cross-tenant records in all four categories, could see its own tenant's accepted and delivered-reported metadata, could not UPDATE consent or call the original 060 writer and could not authorise the other tenant via the synthetic consent-lock function.
- The synthetic callback writer remained a separate password-authenticated SCRAM session, with no direct table INSERT or SELECT and exactly one accepted concurrent writer in the contention check. The disposable database/logins/keys/fixture consent were removed; original PostgreSQL 5432 and canonical production EmpireDB were not migrated or written by these tests.
- **The fixture's SECURITY DEFINER consent lock, fixed test-tenant RLS policies and administrator seeding must never be deployed as production Identity authorization.** Only the original owner-approved, authenticated, tenant-bound consent authority can replace this test machinery.
