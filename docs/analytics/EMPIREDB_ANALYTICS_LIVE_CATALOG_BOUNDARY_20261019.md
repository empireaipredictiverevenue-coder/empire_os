# Empire Analytics — exact local EmpireDB catalogue readiness

19 October 2026 | Safety continuation after Analytics055 source review

## Why
Analytics054 and Analytics055 were committed and tested in isolated
PostgreSQL 18 fixtures. The preflights show staged source integrity;
they DO NOT prove either migration was applied to production EmpireDB.
This wave adds an independent, redacted, fixed-socket read-only
catalogue verifier that can distinguish actual schema state from source
code status without touching commercial, buyer, visitor or payment rows.

## Exact implementation
- empire_os/analytics/catalog_readiness.py:
  a fixed SELECT of pg_catalog only; explicit BEGIN READ ONLY, short
  statement/lock timeouts, no caller-provided SQL or table names.
  Returns schema presence, owner/RLS/trusted-function booleans only.
- scripts/review_analytics_live_catalog_20261019.py:
  strict --read-only. To connect it must be invoked **as the existing
  OS postgres peer user**, not as ubuntu/root or application account.
  Fixed /var/run/postgresql:5432, dbname empiredb, user postgres,
  read-only default transaction, no password/DSN/URL option.
  Fails closed when local peer, schema, privileges or connectivity
  do not match. Redacts all SQL and connection exceptions.
- tests/analytics/test_analytics_live_catalog_pg18_20261019.py:
  real disposable PostgreSQL 18 fixture, after 054 and then after
  055; confirms accurate schema-state detection and a held status
  if a future maintenance role unexpectedly exists. Also tests
  wrong database, unsafe forced RLS, owner/function drift, public
  grants, unsupported flags and no credential/caller SQL options.

## Safe production read-only check — optional operator action

On the authorised EmpireOS Ubuntu server:

    cd /srv/empire_os
    sudo -n -u postgres /srv/empire_os/.venv/bin/python \
      -m scripts.review_analytics_live_catalog_20261019 --read-only

This DOES NOT apply either migration. The OS account must have
pre-existing local peer access; do not change HBA, password custody,
roles or systemd to make the read-only check succeed.

Possible grounded statuses:
- ANALYTICS054_055_NOT_DEPLOYED_IN_OBSERVED_CATALOG
- ANALYTICS054_PRESENT_055_NOT_DEPLOYED
- ANALYTICS054_055_CATALOG_OBJECTS_OBSERVED_RELEASE_HELD
- HELD_* for any drift, collision, unexpected privileges, missing
  local peer or unavailable catalogue.

The third status reports **catalogue objects present** only.
It is NOT an approval for a public collector, a maintenance-login
grant or lawful consent processing. A no-objects result simply
confirms both migrations are source-staged, not live.

## Existing constraints preserved

Never install the writer/maintenance role or grant EXECUTE in this
wave. No automatic timer, production migration or live website tag.
Canonical customer and financial records remain untouched.
Retention period, data-subject verification, privacy notice,
cross-jurisdiction applicability, deletion backups and ASTRA website
consent UX remain unresolved founder/privacy approvals.
Use canonical EmpireDB, not Supabase or a new data store.

Next after read-only state truth: arrange founder's explicit DBA
decision for 054/055 only when retention/legal hold and recovery are
approved; separately design minimally privileged, independently
authenticated maintenance role and consent authority. The analytics
UI continues to show actual visitors/sessions as Not connected.
