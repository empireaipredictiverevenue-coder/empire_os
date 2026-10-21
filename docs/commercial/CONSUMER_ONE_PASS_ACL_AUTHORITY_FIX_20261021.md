# Consumer subscriber: stop the ACL checker loop — one authoritative preflight

**21 October 2026. Production status: IDENTITY PROVISIONED, SERVICE HELD.**

## Actual production evidence

Founder's exact production output at 21 October 2026 was:
```json
{"status":"CONSUMER_ACL_READONLY_HOLD","first_failed_stage":"TABLE_ACL","first_failed_table":"empire_consumer_subscriptions","sqlstate":"42501","production_database_modified":false,"subscriber_rows_fetched":false,"email_sent":false}
```
PostgreSQL SQLSTATE 42501 indicates insufficient privilege performing the check itself; it does **not** demonstrate that business-CRM access was granted. The original protected schema installation verified CRM and public SELECT were denied, but production grants have not yet been independently reaudited now. No role, credential, ACL or HBA change is justified by the failure.

## Root cause of recurring verification failures in design

The original runtime and read-only probes demanded that the intentionally restricted subscriber login call `has_table_privilege` for **other roles** (`empiredb_app`, `empiredb_readonly`, PUBLIC). Even when the consumer login legitimately accesses its own data, production can restrict that cross-principal introspection with 42501. The logical fix is separation of powers, not elevated CRM permissions.

Two changes are provided:

1. `scripts/review_consumer_root_authoritative_20261021.py`: One non-mutating root-local command using two separate authority contexts. First, original local postgres peer identity runs a privileged **BEGIN READ ONLY** catalogue query verifying five forced RLS consumer tables, exact five policies, no app/readonly/PUBLIC effective SELECT, original scoped writer SELECT, one restricted login, and exactly one limited role membership. Second, the actual subscriber login authenticates through original root-owned vault credentials in its own **READ ONLY** transaction and uses `SET LOCAL ROLE`, own effective SELECT and zero-row RLS queries. It never asks the subscriber role to inspect other role permissions. Emits a safe structured report or HOLD (no credentials or personal data).
2. `empire_os/consumer_optin_connection_custody.py`: Restricted runtime connection check no longer asks other principals' effective privileges. It checks its own SELECT and scans table ACL metadata for any grant to an unexpected principal. **Startup must still be independently gated by the privileged admin effective-ACL audit above** before any owner permits service activation.

The original root-owned private verifier is pinned at SHA256:
`7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42`.

## Evidence

- **216 selected unit/regression tests passed** (only original upstream Starlette/AnyIO deprecation warning).
- **Real disposable PostgreSQL 18 test passed** including a genuine synthetic SCRAM password and restricted login, the new root/admin read-only catalogue query + consumer read-only RLS queries, plus deliberately introduced CRM SELECT on one throwaway table causing `CONSUMER_ROOT_ACL_HOLD`. No real production mutation; scratch database destroyed.
- Root check has **no apply mode**. No customer rows, email send, website activation, role change, HBA change, payments or secret leak.

## One final read-only production command

Source SHA256:
`ffac334f36bf2a288040ad91b0d44811df085d387478e9286a38a3f12a1900ee`

Staged nonsecret file:
`/var/tmp/empire-consumer-final-authority-20261021.OhjLDYYY/review_consumer_root_authoritative_20261021.py`

Because staging is Ubuntu-owned, install root-owned 0500 and verify the hash before invoking. This will be **the only remaining identity readiness command** under the existing approved structure unless actual unexpected security drift is found.

```bash
sudo -n install -D -o root -g root -m 0500 \
 /var/tmp/empire-consumer-final-authority-20261021.OhjLDYYY/review_consumer_root_authoritative_20261021.py \
 /usr/local/lib/empire-os/private-consumer/review_consumer_root_authoritative_20261021.py && \
printf '%s  %s\n' \
 'ffac334f36bf2a288040ad91b0d44811df085d387478e9286a38a3f12a1900ee' \
 '/usr/local/lib/empire-os/private-consumer/review_consumer_root_authoritative_20261021.py' \
 | sudo -n sha256sum --check --status && \
sudo -n /srv/empire_os/.venv/bin/python -B \
 /usr/local/lib/empire-os/private-consumer/review_consumer_root_authoritative_20261021.py \
 --read-only
```

A PASS means `CONSUMER_ROOT_AND_LOGIN_READONLY_VERIFIED` and the five per-table privileged catalogue checks all true. If HOLD, **do not start the service**, and treat the report as final owner-level evidence; investigate direct security drift only, not another iterative tier of checkers.

The next build should focus on original authenticated private service + scoped systemd LoadCredential delegation, provider mail receipt and suppression webhooks, and legal/privacy approval. Public opt-in and buyer-data sharing remain OFF.
