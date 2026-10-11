# EmpireOS CRM — single founder pending invitation

**Date:** 11 October 2026. **Production state:** No invitation created by this release's engineering tests.

## Approval and independent recipient evidence

Founder explicitly approved **one pending first-party CRM invitation** for `flavag83@gmail.com`, with no public CRM activation or marketing sends. The connected Gmail OAuth profile was checked in this conversation and returned the same mailbox and owner profile Phil Livesley. This is independent recipient evidence, not merely an email address asserted by a lead.

Canonical existing founder membership: `founder:phil_livesley`, tenant `708efd4b-53b2-43d7-961d-1cecab67f17a`.

Read-only production check using the real, dedicated `empire_crm_auth_login` confirmed `FOUNDER_CREDENTIAL_SLOT_EMPTY`, meaning zero CRM human credential rows match the subject, mailbox or founder tenant. The dedicated service database logins, buyer/prospect readers, tenant binding and persistent passfile are now verified live. Never reprovision those roles or repeat SCRAM/HBA/CONNECT changes.

## Exact gated operation

`scripts/provision_founder_crm_single_invitation.py` wraps the **existing** `prepare_crm_invitation()` and `PostgresCrmInviteOperator.provision()` methods; it does not implement or launch another CRM, invitation engine, service, agent or timer.

The script runs as a privileged operator and sends only a typed pending invitation packet to the `postgres` Unix-socket identity over process stdin, never shell arguments. It checks:
- canonical writable `empiredb` DBA session;
- exactly one active, verified owner membership;
- no existing founder account/email/tenant credentials;
- no existing private founder invitation store;
- unmodified, committed deployment source and an exclusive operation lock;
- the existing operator's recipient/approval evidence checks and single-row `ON CONFLICT DO NOTHING` transaction.

One random token is saved **on EmpireOS only**, in `/var/lib/empire-crm-first-party/founder_invitation/pending_invitation.json` (0700 directory and 0600 owner-only file). The database holds its SHA-256 hash, never the plaintext token. The record starts `pending` with a **48-hour** expiry; the token is **not sent**, and no human password is initialized. The script verifies the pending row after commit without revealing the token. It neither creates a new CRM membership nor enables the HTTP pilot or public route.

**No plaintext token, hash, salted password or other credential should be pasted into ChatGPT, any log or a Git commit.** The protected file is strictly for later verified transactional invitation delivery, when the private CRM service is ready to accept invitations.

## Single approved production command

Run the preflight as root:

```bash
cd /srv/empire_os
sudo -n /srv/empire_os/.venv/bin/python \
  scripts/provision_founder_crm_single_invitation.py --preflight
```

Expected `CRM_INVITATION_PREFLIGHT=ONE_ACTIVE_FOUNDER_NO_CREDENTIALS` and `CRM_INVITATION_RESULT=PREFLIGHT_READY_NO_CHANGES`.

Then, **only if** preflight passes, execute once:

```bash
sudo -n /srv/empire_os/.venv/bin/python \
  scripts/provision_founder_crm_single_invitation.py \
  --apply --approved-one-founder-crm-invitation
```

Expected:
```text
CRM_INVITATION_TOKEN=SECURED_ON_SERVER_NOT_SENT
CRM_INVITATION_DB_TRANSACTION=ONE_PENDING_ROW_COMMITTED
CRM_INVITATION_POSTCOMMIT=ONE_PENDING_FOUNDER_VERIFIED
CRM_INVITATION_EMAIL_SENT=NO
CRM_INVITATION_HTTP_ACTIVATED=NO
CRM_INVITATION_RESULT=ONE_PENDING_INVITATION_VERIFIED
```

**Never blindly retry** if the status is uncertain or any check fails, because the row may have committed or the private token vault may be populated. Inspect metadata and reconcile before doing anything else. Never send the raw token to an unverified mailbox; the linked Gmail account is now verified but no send is authorized by this operator.

## Proofs and remaining boundary

Focused wrapper tests: `tests/test_provision_founder_crm_single_invitation.py`. The existing PostgreSQL operator integration tests are `tests/test_revenue_crm_pilot_operator.py`. Read-only service mount and tenant tests were previously green, and direct production buyer/prospect/owner membership-reader probes passed.

The CRM human login and bearer JWT are **not yet active**. Before token delivery, provision a durable 0600 Ed25519 signing key and exact private JSON pilot config, verify `PGPASSFILE`, then install and test only the loopback service at **127.0.0.1:8783** with no Cloudflare/public ingress, no automated mail, outbound or payments. The invitation expires after 48 hours and should be redeemed securely before then.
