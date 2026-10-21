# Empire AI — Consumer subscriber private login proof and runtime assembly

**21 October 2026. Scope: verified source and isolated tests; service remains HELD.**

## Confirmed deployed foundation

Founder supplied original privileged production receipts on 21 October 2026:

- Consumer schema `CONSUMER_SCHEMA_INSTALLED_READBACK_VERIFIED`: 5 FORCE RLS tables, 5 policies, dedicated NOLOGIN scoped writer, existing business-CRM grants sealed on those five tables
- Restricted consumer login/keys `PRIVATE_IDENTITY_PROVISIONED_SERVICE_HELD`: one login, one restricted writer membership, root-owned 0700 vault, independent 256-bit lookup HMAC/token HMAC/AES-GCM keys in 0600 files; service/public collection/outbound disabled
- Privileged pgBackRest metadata validated, newest completed backup was 24.3h old (not an independent restore test)

The source code must not infer that a successful account creation alone proves an authenticated production session.

## New read-only live proof (NO service activation)

`scripts/review_consumer_private_identity_session_20261021.py` verifies:

1. Privileged root process, non-symlink root-owned vault (0700), two non-linked root-owned secret files (0600), exact original private login password format and exactly three distinct 256-bit cryptographic keys
2. An actual **localhost SCRAM authentication to EmpireDB** as `empire_consumer_optin_login` using the original protected password, without printing or persisting the password, keys or provider credentials
3. A READ ONLY transaction, original `session_user`, exactly one non-inheriting/settable/admin-disabled membership in `empire_consumer_optin_writer`, no superuser/BYPASSRLS privilege and no unrelated role grants
4. `SET LOCAL ROLE empire_consumer_optin_writer` inside the read-only transaction, five FORCE RLS tables owned by `empiredb_migrator`, exact five original writer policies, no CRM/readonly/PUBLIC SELECT permission
5. Explicit `SELECT 1 ... LIMIT 0` through the actual RLS identity: **zero subscriber records are returned**. Nothing is inserted, altered, exported or sent

The read-only probe fails closed and prints **only generic redacted status** on any secret, database or ACL error. It cannot be used to activate the service.

The tested source SHA256 is:

`7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42`

The nonsecret staged file exists at:

`/var/tmp/empire-consumer-private-review-20261021.12rINJlh/review_consumer_private_identity_session_20261021.py`

**IMPORTANT:** The staged file is Ubuntu-owned. Install exact matching bytes to a root-owned/0500 path before invoking as root. No other secrets should be copied or printed.

```bash
sudo -n install -D -o root -g root -m 0500 \
  /var/tmp/empire-consumer-private-review-20261021.12rINJlh/review_consumer_private_identity_session_20261021.py \
  /usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py

echo "7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42  /usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py" \
 | sudo -n sha256sum --check --status && \
sudo -n /srv/empire_os/.venv/bin/python -B \
  /usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py \
  --read-only
```

Success status to verify independently: `CONSUMER_PRIVATE_IDENTITY_LIVE_READONLY_VALIDATED`. No service unit needs a restart.

## Pure private backend assembly (not deployed)

`empire_os/consumer_optin_private_runtime.py` combines the existing private `ConsumerPostgresRepository`, `PrivateConsumerConnectionFactory`, first-party HMAC suppression reader, `PrivateConsumerOptinService` and transactional Resend sender. The only credential source is explicit injection of parsed **service-delegated credentials** (future `systemd LoadCredential` custody); it does not open the root vault, generic `/etc/empiredb.env`, or CRM DSNs and it does not mount a public router or start a daemon.

Everything is fail-closed by default:
- private repository custody flag disabled, confirmation sender approval disabled, independently verified sender-domain flag disabled
- a fresh original restricted DB session and all ACL/RLS checks are required for signup and withdrawal readiness if custody is later approved
- a sender outage must not revoke subscriber withdrawal rights once private custody is separately approved
- no provider network call is attempted during module import or backend construction

Live sender, web/API routing, public signup, privacy notice, and delegated secret-reader OS identity all require **separate explicit owner approvals**. The protected root vault must never be opened by the public gateway.

## Testing

- **180 selected pytest tests passed** after this release, one existing upstream Starlette/AnyIO deprecation warning.
- `pg_virtualenv -v 18 /bin/bash scripts/test_consumer_private_identity_pg18_20261021.sh` also passed: synthetic SCRAM password and real PostgreSQL 18 member identity, read-only session probe, five protected RLS tables and denied CRM access, followed by revocation/denial. Disposable database automatically destroyed.
- Never copied or read the actual production password/keys during source testing or staging; no service or customer email was activated.

## Next gates

Read and verify the exact root-owned proof output; then implement a private systemd process and securely delegate only its own scoped credentials, not the full root vault. Prepare privacy/legal confirmation and unsubscribe link behaviour and provider webhook signatures. Explicitly separate first-party marketing consent from any third-party buyer referral. Public SEO guide can be reviewed without enabling subscriber collection.
