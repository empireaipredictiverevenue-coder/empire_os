# Consumer opt-in: production role and activation custody — 20 Oct 2026

**Status: staged migrations, live Resend domain verified, NO personal-data collection authorised.**

## Additional implementation

A new separate migration `migrations/empiredb/058_consumer_optin_private_role_staged_20261020.sql` creates exact-purpose RLS policies and table privileges for a *pre-existing, restricted* role named `empire_consumer_optin_writer`. **The migration cannot create a login or directly connect a live service.**

The database administrator must independently verify all of these before any production apply:

- Recent pgBackRest backup under privileged local identity. The available unprivileged shell cannot read `/etc/pgbackrest/pgbackrest.conf`; the existing sanctioned backup review script returns `HOLD_ROOT_LOCAL_READ_REQUIRED` when run without root. **No fresh backup verification was established here.**
- An independently approved restricted migrator (`empiredb_migrator`, NOLOGIN/NOBYPASSRLS) and separate prepared `empire_consumer_optin_writer` with NOLOGIN, NOINHERIT, NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE, NOREPLICATION. Role creation and membership must be performed by the existing DBA under separate privileged approval.
- Apply 057 and 058 against the canonical EmpireDB in order only, never in parallel with another owner migration; verify exactly five forced-RLS tables and five scoped policies, no application/CRM/public grants, consent append-only trigger and provider receipts. The 058 SQL rejects incomplete custody and existing policies rather than silently overwriting production objects.
- Do **not** make `empiredb_app` or the existing CRM/Sales/Analytics readers members of `empire_consumer_optin_writer`. The standalone, purpose-scoped consumer service identity and protected key material must be independently provisioned, with restricted connection privileges and audit receipts.

## Real database proof (isolated)

```bash
cd /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
./scripts/run_consumer_optin_ephemeral_db_probe_20261020.sh
```

The script creates a disposable PostgreSQL 18 `pg_virtualenv` cluster with a synthetic `empiredb_migrator` and prepared `empire_consumer_optin_writer`. It executes migrations 057 and 058, verifies five tables with forced RLS, no public access, five scoped policies and a NOLOGIN private writer. With `SET ROLE`, it then exercises **real original consent, encrypted pending signup, provider-confirmed token, verified subscription, unsubscribe, suppression, replay denial, re-enrolment hold and append-only consent history**. The fixture simulates provider sends (zero real emails) and drops the cluster automatically. No production SQL is executed by this test.

The 126 selected tests, including the RLS invariant checks, passed on 20 October (one dependency deprecation warning).

## Real email provider status

The account's Resend domains `mail.empire-ai.co.uk` and `empire-ai.co.uk` were independently reported `verified`, `sending enabled`; the original server has a private Resend key-configuration field. The adapter `empire_os/consumer_optin_resend_sender.py` is **tested but not connected to live opt-ins**. It requires a trusted suppression reader, scoped provider credentials and explicit consumer transactional sender authority. It sends no email without those dependencies.

## Privacy and owner review

The actual `https://empire-ai.co.uk/privacy` page is public HTTP 200 but independent signoff of own-brand homeowner email updates and their dedicated retention/unsubscribe/deletion rules is still missing. Draft copy is under `docs/commercial/ROOFING_OWN_BRAND_OPTIN_NOTICE_FOR_REVIEW_20261020.md`; its existence is **not legal approval**.

The informational free guide and email-preferences page are built and static-preview tested, but are not released under the original website content provenance/approval mechanism. Live `/roofing/cost-guide` and `/roofing/email-preferences` are 404, as is the subscriber status endpoint. Existing `/roofing` remains HTTP 200.

## Activation must remain staged

Only after independently verified DBA backup and migration receipts, real protected service credentials/key custody, current original privacy notice approval, completed reviewed-content release, actual provider-send acceptance, functioning withdrawal/suppression and one real consenting participant should the status endpoint become `OPTIN_COLLECTION_ENABLED`.

None of the following happened in this task: production migration, customer email capture, real confirmation send, unapproved marketing, lead resale or customer payment.
