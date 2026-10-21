# Consumer subscriber — production identity READONLY_HOLD triage

**Date:** 2026-10-21. **Status:** nonmutating diagnostic prepared; actual first failing production stage not yet known.

## Original evidence

Founder executed source-pinned, root-owned live private session probe `review_consumer_private_identity_session_20261021.py --read-only`. The original privileged result:

```json
{"email_sent":false,"production_database_modified":false,"status":"CONSUMER_PRIVATE_IDENTITY_READONLY_HOLD"}
```

Earlier privilege installer claimed `PRIVATE_IDENTITY_PROVISIONED_SERVICE_HELD` after creating an isolated SCRAM LOGIN, single writer-role membership, root-owned vault and three independent cryptographic keys. These are distinct observations. Do not assume a successful role creation proves successful live login or RLS/session readiness.

The first probe masks all exceptions, correctly avoiding credential leaks but preventing root-cause isolation.

## New first-failure-stage diagnostic

`scripts/diagnose_consumer_private_identity_hold_20261021.py` is **read-only only** and pins the existing original root-owned review source to SHA256:

`7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42`

It checks, sequentially, source integrity, original owner-only secret vault/key formatting, localhost SCRAM authentication, `SET TRANSACTION READ ONLY`, original login identity, safe role attributes and its exclusive role membership, `SET LOCAL ROLE`, actual writer identity, five FORCE RLS table/owner checks, exact five scoped policies, per-table CRM/readonly/PUBLIC denial and `SELECT 1 LIMIT 0` without fetching subscriber data.

It emits `CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_PASS` or `CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_HOLD` and **only** the first failing stage name from a hardcoded allowlist. No SQL exception strings, passwords, key material, DSN, row contents, provider details or emails appear in output. It has no apply/deploy/alter/insert/send mode. All DB work is in a read-only transaction and attempted against localhost only.

Positive full probe through real disposable PostgreSQL 18 test fixture passed. All 14 new failure-stage/redaction unit tests passed; **194 selected regression tests passed** total (one preexisting third-party AnyIO deprecation warning).

New staged source SHA256:

`1e62783c710a09609b3f69790d1e0ebbbf40f0ed901d3fc43ce30609d92bc306`

Staged only at:

`/var/tmp/empire-consumer-private-hold-diagnostic-20261021.0uQ4Nq95/diagnose_consumer_private_identity_hold_20261021.py`

## Authorized local read-only command

Run in the founder's local EmpireOS privileged operator terminal. The staged path is Ubuntu-owned so **must be copied to a root-owned 0500 location and verified before execution**. The target original review script is already root owned and digest-pinned; no overwrite of that original is necessary.

```bash
sudo -n install -D -o root -g root -m 0500 \
 /var/tmp/empire-consumer-private-hold-diagnostic-20261021.0uQ4Nq95/diagnose_consumer_private_identity_hold_20261021.py \
 /usr/local/lib/empire-os/private-consumer/diagnose_consumer_private_identity_hold_20261021.py && \
printf '%s  %s\n' \
  '1e62783c710a09609b3f69790d1e0ebbbf40f0ed901d3fc43ce30609d92bc306' \
  '/usr/local/lib/empire-os/private-consumer/diagnose_consumer_private_identity_hold_20261021.py' \
 | sudo -n sha256sum --check --status && \
sudo -n /srv/empire_os/.venv/bin/python -B \
 /usr/local/lib/empire-os/private-consumer/diagnose_consumer_private_identity_hold_20261021.py \
 --read-only
```

**Required continuation:** inspect the returned `first_failing_stage` and fix its specific cause after confirmation, with existing isolation and no external send. Do **not** rotate secrets, change PostgreSQL roles/HBA, activate web or email, or bypass the original check until the read-only evidence grounds an approved minimal remedy.

No production database writes, subscriber records, or outbound email were performed by this triage build.
