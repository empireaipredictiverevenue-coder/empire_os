# Empire AI consumer subscriber: dedicated private identity & cryptographic custody

**21 October 2026 — BUILT AND TESTED, NOT INSTALLED IN PRODUCTION.**

## Verified existing production foundation
Founder successfully applied the approved consumer schema release under EmpireDB:
`CONSUMER_SCHEMA_INSTALLED_READBACK_VERIFIED`, 5 FORCE RLS tables, 5 scoped policies, NOLOGIN writer, CRM default grants sealed on just the five subscriber tables; no service login. The approved schema digest was `fe9da8e0a8871e78103941729fb893c891a542286531a283e0d40f2846026cd1`. No new opt-ins or outbound are authorised by this schema.

## New identity release (preparation only)
`scripts/provision_consumer_private_identity_20261021.py` is a root-only control with two modes:
- `--read-only`: uses original local postgres peer identity to check correct database, migrator, exactly five protected tables/policies, no CRM table access, NOLOGIN writer, absence of the separate service login, a localhost SCRAM HBA rule without parsing errors, and a safe empty secret-vault target. Redacts credentials; never mutates.
- `--apply-owner-approved EXACT_SHA256`: separate **future authorisation required**. Refuses non-root and any digest mismatch; takes an exclusive operator lock and reruns all checks. Generates a separate cryptographically random login password plus three distinct private 256-bit keys (email lookup HMAC, token HMAC and AES-GCM encryption) in root-owned `/etc/empire/consumer-optin` with 0700 directory and 0600 files. The PostgreSQL CREATE ROLE transaction uses a SCRAM verifier—not plaintext password—in submitted SQL; creates only `empire_consumer_optin_login` with NOINHERIT/NOSUPERUSER/NOBYPASSRLS, one membership in `empire_consumer_optin_writer` with INHERIT FALSE/SET TRUE/ADMIN FALSE, a local DB CONNECT grant and a 5-connection cap. No CRM/migrator memberships, HBA changes, schema changes, service start, public routes or sends. A transactional guard rechecks tables, RLS/policies and ACL isolation just before CREATE ROLE. Secret-write or DDL failure cleans newly created credentials; postcommit anomaly preserves credentials and returns a HOLD for supervised investigation.

**Approved-for-review code digest:**
`477671838ef673880d1ecda409c0118824d7d4e2e243aa04a8749cc85b8c87c4`

Do not confuse this with schema SHA; source hash is a new, unapproved production capability.

## Protected operator code staging
A nonsecret source copy was staged at:
`/var/tmp/empire-consumer-private-identity-20261021.2qlhjkk3/provision_consumer_private_identity_20261021.py`

Because this folder is Ubuntu-owned, **do not execute it directly as root**. For the privileged read-only preflight only, first copy the verified exact bytes into a root-owned, not Ubuntu-editable directory, then verify the checksum again.

```bash
sudo -n install -D -o root -g root -m 0500 \
 /var/tmp/empire-consumer-private-identity-20261021.2qlhjkk3/provision_consumer_private_identity_20261021.py \
 /usr/local/lib/empire-os/private-consumer/provision_consumer_private_identity_20261021.py

echo "477671838ef673880d1ecda409c0118824d7d4e2e243aa04a8749cc85b8c87c4  /usr/local/lib/empire-os/private-consumer/provision_consumer_private_identity_20261021.py" \
 | sudo -n sha256sum --check --status && \
sudo -n /srv/empire_os/.venv/bin/python -B \
 /usr/local/lib/empire-os/private-consumer/provision_consumer_private_identity_20261021.py \
 --read-only
```

The original user's explicit production schema approval DOES NOT authorise a new LOGIN, password storage or key material. **Do not invoke `--apply-owner-approved` until a separate explicit founder approval for this exact identity digest following the read-only output.** Fresh privileged pgBackRest backup metadata should be rechecked first.

## Evidence of implementation
- The real PostgreSQL 18 throwaway fixture `scripts/test_consumer_private_identity_pg18_20261021.sh` builds actual consumer schema 057→059→058, creates an independently authenticated login using a generated SCRAM verifier, verifies correct restricted connection, 0 CRM/readonly access to customer tables and denial when writer membership is revoked. **Passed**.
- The existing real PostgreSQL login and subscriber lifecycle fixture also passed: double opt-in, simulated sender, confirmed subscriber, unsubscribe, suppression and re-enrolment hold using the restricted login; all contacts synthetic and database destroyed.
- **158 selected unit/regression tests passed** across private role/sender/repository/gateway and new root-vault behavior. The new unit tests verify no plaintext credential in PostgreSQL SQL, key separation, root-only vault file modes, rollback of half-written secrets, digest gates, denied non-root execution, and conservative postcommit HOLD. One upstream AnyIO deprecation warning.

## After provision (still separate approvals)
A distinct private service runtime with controlled OS user/credential delegation (e.g. systemd `LoadCredential`), rate limiting, separate explicit transactional Resend sending approval, verified current suppression and bounce callbacks, and original legal/privacy/retention approval must be completed. The public guide and email preferences route remain unpublished, and original first-party consent does not authorise buyer-sharing. No real subscriber data, payment, marketing send, CRM import or buyer referral has occurred in this stage.
