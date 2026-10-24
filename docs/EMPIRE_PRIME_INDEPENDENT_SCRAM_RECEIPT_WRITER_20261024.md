# Empire AI / Original PRIME — Independently Authenticated Callback Writer
\n
\n**Date:** 24 October 2026
\n**Original branch:** `feature/prime-universal-evidence-fusion-20261024`
\n**Authority:** Isolated disposable PostgreSQL 18 fixture, **NOT production or real provider authentication**.
\n
\n## Exact original continuation
\n
\nPrevious original flagship build proved a two-signature **fictional** ASTRA callback can safely exercise held EmpireDB migrations 057–060 using a temporary role whose effective permissions lack 059 SELECT/INSERT. But the test opened its writer connection as a fixture superuser and switched effective role using `SET LOCAL ROLE`. That is useful for testing function SQL permission, **not proof of a separate login or safe service credentials**.
\n
\nThis milestone replaces the writer portion with **a genuinely separate disposable PostgreSQL LOGIN** using SCRAM-SHA-256 over loopback, retaining the same original ASTRA callback, original 060 function and 059 callback ledger. No separate platform, database or notification service was created.
\n
\n## Implemented
\n
\n- `scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh`: original `pg_virtualenv -t` wrapper creates a temporary PostgreSQL 18 `empire_timer_fixture` database at port 5433, verifies its actual `/tmp/pg_virtualenv.*/data/18/regress` directory and installs the **held** 057–060 migrations. It creates a **test-only LOGIN** `timer_fixture_gateway_login` with a high-entropy ephemeral secret under PostgreSQL SCRAM-SHA-256.
\n- The wrapper prepends a rule for **only that temporary database/login on 127.0.0.1/32** to its temporary `pg_hba.conf`, reloads PostgreSQL and verifies that the expected rule was accepted. It then exercises separate loopback sessions. Passwordless and deliberately incorrect-password logins are rejected; only the correct temporary password succeeds.
\n- Extra PostgreSQL authentication rules explicitly reject this login on all *other* databases and connection paths. An independent connection to `postgres` with the correct password was refused. The temporary password is sent into psql through stdin for fixture-role creation, not command-line arguments.
\n- The fixture login has NOINHERIT, no superuser, no RLS bypass, no CREATEDB, no CREATEROLE and no migrator membership. Its sole grant outside generic CONNECT/USAGE is **EXECUTE on original held function `empire_prime_timer_receipt_record_held`**. PostgreSQL confirms direct 059 SELECT=false and INSERT=false, while EXECUTE on 060=true; a real connection as the restricted login fails a direct table SELECT.
\n- `scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py` adds `_actual_fixture_login()`, which authenticates as the disposable login, verifies actual `session_user`, `current_user`, database, port and rights, and performs 060 writes on **that separate session**, not through `SET ROLE` on a privileged session. The original connection guard refuses port 5432 and verifies the temporary cluster's actual data directory before the fixture can run.
\n- Only the **exact cryptographically verified fictional provider payload** supplies provider/timer/callback metadata; an independent separately signed fictional consent-owner record must validate. The original identity fixture still uses an administrative test connection to read a **fictional** consent table and original claim. Its `FOR SHARE` lock is held while the separate writer transaction commits. This is a synthetic authority simulation, not real Identity service permission.
\n- The existing replay, signature forgery, revoked fictional consent, acceptance-before-delivered and database claim-binding behaviours still pass. Two **separate authenticated login sessions** contend to record an ACCEPTED callback for one fictional timer; exactly one record survives, with the second rejected by the original 059 trigger/060 serialization.
\n
\n### Tested without contacting production
\n
\n```bash
\ncd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
\npg_virtualenv -t bash scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh
\nPYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
\n  tests/test_prime_timer_pg_restricted_writer_060_20261024.py \
\n  tests/test_prime_signed_gateway_db_bridge_fixture_20261024.py \
\n  tests/test_prime_flagship_notification_gateway_shadow.py
\n```
\n
\n**53 focused tests passed** with one inherited Starlette/anyio warning. The broader original-system regression separately passed **1,252 tests** with the same inherited warning; the additional original conversation-linkage suite passed **5 tests**. Those two latter sets were run as separate pytest invocations, not as a single aggregate report. The actual disposable PostgreSQL script emitted:
\n
\n- `EPHEMERAL_SCRAM_LOGIN_AUTHENTICATED=true`
\n- `SCRAM_WRONG_PASSWORD_AND_HIGH_PRIVILEGES_DENIED=true`
\n- `SCRAM_OTHER_DATABASES_REJECTED=true`
\n- `REAL_SCRAM_LOGIN_NO_TABLE_PERMISSIONS=true`
\n- `SCRAM_LOGIN_DIRECT_TABLE_SELECT_DENIED=true`
\n- `SCRAM_LOGIN_TWO_WORKERS_ONE_CALLBACK=true`
\n- `SIGNED_GATEWAY_060_RESTRICTED_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0`
\n
\nThe separate PostgreSQL test cluster, fixture login, its SCRAM verifier/password and its receipt rows were destroyed at fixture exit. Production main PostgreSQL 5432 was not migrated or changed.
\n
\n## Non-negotiable next owner boundary
\n
\n1. **Original EmpireDB/Security:** approve or revise held 057–060 roles, forced RLS and the restricted writer privilege, then provision managed production service credentials through existing original security custody. A temporary SCRAM password does NOT confer production authority.
\n2. **Original Identity/Privacy:** replace privileged fictional consent/claim readers with authenticated scoped readers and enforce revocation/tenant/device scope atomically. Treat real owner attestation and explicit opt-in as required, not an accepted synthetic Boolean.
\n3. **Original Notification:** select **one** authorised provider sandbox and adapt the provider's *actual* signed callback protocol, with independent signing keys, clock/nonce policy, acceptance vs actual device-delivery semantics and privacy protection.
\n4. **Original ASTRA/Scheduler:** connect the authenticated original gateway to real provider receipt custody and reconcile uncertain dispatches without blind retry. Never equate a 060 custody row with notification delivery.
\n5. **Original Founder/Voice:** keep original private cockpit NOT_CONNECTED until a consenting test identity and an authentic device receipt have been independently verified.
\n
\nThis engineering proof establishes separate database authentication and least-privileged effective write rights for the fictional fixture, **not** an actual user reminder, live notification, independent £250k valuation or new revenue.
\n
\n**One EmpireOS. One original EmpireDB. One original PRIME, ASTRA, Digital Twin and Voice Lab.**
\n