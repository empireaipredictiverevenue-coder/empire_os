# EmpireOS JEV — Wave 14 Real SMTP Acceptance Prerequisite Gate

Date: 2026-10-14
Isolated branch: feature/jev-gtm-v2-20261014
Starting HEAD: a76bb49a
Mode: read-only / no active mail receiver / no production deployment.

## Production truth inspected

The Wave 13 first-party candidate Postfix configuration was approved only for
offline inspection, not live mail operation. Wave 14 attempted to establish
whether real Postfix SMTP RCPT acceptance could be tested in a safe isolated
environment without changing the production mail host.

- Docker binary exists; current ubuntu user is refused access to the Docker
  daemon socket. No containers were started.
- User namespace creation was denied while writing its UID map. No rootless
  namespace was created.
- Installed Postfix binaries (postfix, postconf, postmap) do not exist.
  Dedicated postfix user and postdrop group do not exist.
- The Canonical Ubuntu Postfix 3.10 package and libnsl2 dependency were
  downloaded and extracted under temporary directories and destroyed after
  each check. They were NOT installed.
- Real Postfix parser checks (postconf -n and postconf -M) succeeded during
  Wave 13; these only establish syntax parsing of the isolated config.
- postmap compilation failed because uninstalled server identities are
  absent. Temporary fixture user/group substitutions also failed under
  Postfix's privilege-group constraints. No host identities were created.
- No real postmap database certified; no SMTP daemon launched, RCPT checks,
  DKIM/SPF/DMARC validation, or message delivery observed.

STOP criterion: do not fabricate Postfix service identities or relax security
to force acceptance testing on the shared production host. A distinct
approved isolated container or VM is required first.

## Wave 14 implementation

empire_os/owned_postfix_receiver_preflight.py:
- Pure assessment of injected binary inventory, nonroot mail-owner user,
  dedicated postdrop group, nonroot default_privs account and disallowed
  privilege group collisions.
- Isolated SMTP runtime availability must be separately verified.
- Always returns HOLD_POSTFIX_RECEIVER_ACTIVATION with precise blocker codes.
  Binary or config presence does not prove real SMTP delivery, relay denial
  or original transport provider authenticity.
- Never reads secrets, original messages, tenant data or contacts.

scripts/probe_owned_postfix_receiver_prerequisites.py:
- Default invocation does not inspect host.
- Explicit --read-only checks only fixed binary presence and pwd/grp
  OS identity metadata, without any network or message access.
- Does not execute Postfix, start Docker, create namespace, download packages,
  modify DNS, install services, bind sockets or access the database.
- Emits privacy-safe machine-readable HOLD and returns exit code 2.

tests/test_owned_postfix_receiver_prerequisites.py:
- Covers missing service identity, conflicting privilege GIDs, unknown or
  spoofed metadata, non-authoritative complete inventories and no-default-IO.
- Targeted tests: 54 passed, 1 pre-existing Starlette/AnyIO warning.
- Full JEV/CRM/mailbox/research gauntlet: 819 passed, 10 subtests passed, zero failures and one existing AnyIO/Starlette warning. Python syntax, Git diff and frontend TypeScript checks all passed.

## Independently observed read-only release snapshot

The probe returned HOLD_POSTFIX_RECEIVER_ACTIVATION with:
- POSTFIX_BINARIES_NOT_INSTALLED
- UNPRIVILEGED_POSTFIX_MAIL_OWNER_MISSING
- POSTDROP_SETGID_GROUP_MISSING
- ISOLATED_SMTP_RUNTIME_NOT_PROVEN
- LIVE_SMTP_ACCEPTANCE_UNTESTED
- FIRST_PARTY_INGRESS_CUSTODY_UNVERIFIED
- MAIL_TRANSPORT_AUTHENTICATION_UNAUDITED
- EXISTING_MX_CUTOVER_UNAPPROVED

The live mail.empire-ai.co.uk MX remains routed to SES and was not changed.

## Next exact acceptance environment

The next owner-controlled test requires a separate disposable container/VM
with founder-approved isolated runtime access; legitimate Postfix/postdrop
identities; proper filesystem and network isolation; genuine postmap
compilation; one exact recipient acceptance; rejected unknown, bare reply@,
catch-all and external-relay recipients; authenticated DNS/TLS/DMARC setup;
signed original SMTP receipt linked to the existing Wave 12 verifier; no
inbound message loss and tested rollback. Migration 051, signer keys, MX
cutover and outbound actions remain separately approval-gated.

Wave 14 is a tested HOLD gate, not a live sovereign mail receiving service,
and provides zero independently authenticated buyer conversations.
