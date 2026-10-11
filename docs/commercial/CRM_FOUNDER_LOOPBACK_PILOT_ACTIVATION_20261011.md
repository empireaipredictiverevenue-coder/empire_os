# EmpireOS founder CRM — approved private loopback activation, 11 October 2026

## Exact verified state

The founder explicitly approved activating **only** the founder CRM pilot on `127.0.0.1:8783` and sending one transactional invitation to the verified connected Gmail owner `flavag83@gmail.com`. No Cloudflare ingress, public CRM service, unrelated systemd reload/restart, marketing emails, payments, credentials in logs or multi-tenant database migrations are authorized.

Already verified from production:
- Exactly three SCRAM CRM dedicated logins, own restricted password file, tenant-scoped membership and read-only buyer/prospect views.
- Founder invitation: `pending`, unredeemed, SHA-256 token hash in EmpireDB; plaintext token **only** in `/var/lib/empire-crm-first-party/founder_invitation/pending_invitation.json` (mode 0600).
- Token expiry: **2026-10-13T10:00:42Z**, equivalent to 11:00:42 BST.
- Existing founder CRM service unit `deploy/systemd/empire-revenue-crm-pilot.service` uses `User=ubuntu`, `127.0.0.1:8783`, `--no-proxy-headers`, hardened systemd sandbox.
- Shared CRM runtime remains **not installed, not publicly exposed** as of preparation.

## Three scoped scripts (do not create an alternative platform)

1. `scripts/stage_founder_crm_pilot_private.py`: service user stages a new Ed25519 signing key and complete founder-only private JSON under `/var/lib/empire-crm-first-party`, and a staged environment file; all mode 0600, with unchanged database secret file. Checks exact founder invite, expiry, private owners, one tenant/three known roles, offline FastAPI routes, 401 unauthenticated reads, no docs, fresh live member and buyer/prospect DB readers. It refuses partial/mismatched previous state; no HTTP startup.
2. `scripts/deploy_founder_crm_loopback_service.sh`: root-only, exact approval flags, checks committed unchanged unit/installer, staged offline runtime verification, empty port 8783, systemd unit validity, no preexisting installed unit/environment. Installs the unit and root-only `/etc/empire/crm-pilot.env`; **starts only** the private pilot, without enabling on reboot. Live health 200, unauthenticated CRM 401, docs 404, exact bound socket `127.0.0.1:8783` and systemd active required. Stops service on failed live proof, preserves state for manual reconciliation; no blind retry.
3. `scripts/redeem_founder_crm_invitation_local.py`: user-interactive, single-purpose SSH TTY action only **after activation**; reads the existing token directly from the restricted server vault, asks founder to choose/confirm a password privately with getpass, calls the existing first-party `/accept-invite` route over hardcoded loopback, then actual `/login` and authenticated read of founder-scoped prospect/buyer routes. Prints only status receipts; **never prints tokens, passwords, JWTs or customer rows**. HTTPConnection to `127.0.0.1:8783` never follows redirects or proxy settings. Repeated redemption is not permitted by the underlying database.

## Activation sequence

First stage and verify the private runtime as the service account (not as root):

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python scripts/stage_founder_crm_pilot_private.py --preflight
/srv/empire_os/.venv/bin/python scripts/stage_founder_crm_pilot_private.py --stage-once
```

Expected `CRM_PRIVATE_STAGE=READY` followed by `CRM_PRIVATE_STAGE=CONFIG_SIGNER_PGPASS_OFFLINE_VERIFIED`. If already staged, use `--verify` instead of creating any more private keys.

The root-only service activation, after the approved private staging:

```bash
cd /srv/empire_os
sudo -n bash scripts/deploy_founder_crm_loopback_service.sh --preflight &&
sudo -n bash scripts/deploy_founder_crm_loopback_service.sh --apply --approved-founder-loopback-only
```

Expected `CRM_LOOPBACK_DEPLOY=PREFLIGHT_READY_NO_CHANGES` then `CRM_LOOPBACK_DEPLOY=APPROVED_PRIVATE_SERVICE_VERIFIED`. Any blocked/uncertain result: stop and inspect actual config, service and bind evidence, no blind repeated deployment.

**Only after live service proof** send one plain transactional email to `flavag83@gmail.com`, with local founder setup instructions **but no token in the email**. This is intentionally safer: the token remains on the private server until redeemed over SSH TTY; no email containing the token is needed. The connected Gmail account is the verified receiving mailbox; do not use third-party mass mail transport, cold outreach, or unconfigured founder-domain sender.

Founder first login after activation:

```bash
ssh -t ubuntu@62.210.95.205 'cd /srv/empire_os && /srv/empire_os/.venv/bin/python scripts/redeem_founder_crm_invitation_local.py --interactive-first-login'
```

If already logged into EmpireOS interactively:

```bash
cd /srv/empire_os
./.venv/bin/python scripts/redeem_founder_crm_invitation_local.py --interactive-first-login
```

No passwords are ever pasted into ChatGPT, Gmail, Git or shell arguments. Expected success: `CRM_FOUNDER_SETUP=FIRST_PARTY_LOGIN_VERIFIED`, plus authenticated prospects/buyers receipts. Direct SSH terminal remains required because the service is deliberately **not publicly accessible**. The pilot is start-only; verify before treating it as persistent across server reboot.

## Tests

`tests/test_stage_founder_crm_pilot_private.py` and `tests/test_founder_crm_loopback_release.py`, plus existing `tests/test_revenue_crm_pilot_service.py` and `tests/test_revenue_crm_pilot_activation.py`. Retain the exact tested service file, not a new Hub or separate login agent.

No token email until the private pilot has demonstrably started. No guest/public access.
