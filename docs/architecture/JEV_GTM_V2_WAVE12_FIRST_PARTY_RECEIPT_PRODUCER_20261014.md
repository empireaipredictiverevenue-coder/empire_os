# EmpireOS JEV Wave 12 — Sovereign First-Party Mail Receipt Producer

Date: 2026-10-14
Worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Branch: `feature/jev-gtm-v2-20261014`
Starting commit: `0cfc4354`
Default authority: OBSERVE, zero paid external APIs, no production deployment.

## Verified current receiving reality

The live bounded production read established:
- `mail.empire-ai.co.uk` **MX** resolves to `10 inbound-smtp.us-east-1.amazonaws.com.` (Amazon SES).
- `mail.empire-ai.co.uk` **A** resolves to `216.128.149.56`, not the known EmpireOS host `62.210.95.205`.
- Root `empire-ai.co.uk` MX resolves to Google.
- Existing Resend inbound webhook service on 8097 reports active but its webhook status alone does not prove messages flow through SES MX.
- Current Founder-owned IMAP reader is unconfigured, prepared canonical view credential/drop-in absent.
- No Postfix, OpenDKIM, OpenDMARC, Dovecot, rspamd or other local mail receiver executable was installed, and no listeners were visible on the standard local SMTP/IMAP ports checked.
- No real signed first-party ingress transport event exists in the inspected evidence.

Therefore NO LIVE MX CHANGE, SMTP LISTENER, CREDENTIAL PROVISION, EMAIL SEND, MAIL RECEPTION, DNS UPDATE OR PRODUCTION MIGRATION is in this wave.

## Completed working integration (offline engineering)

`empire_os/owned_ingress_receipt_producer.py` adds a bounded owner-side receipt producer, deliberately **not** another JEV agent or service.

1. Receives original raw RFC message bytes (maximum 512 KiB) and separate SMTP-envelope recipient from a future authenticated local MTA delivery boundary. The MIME `To`, `Authentication-Results`, `Received`, sender-reported timestamp and `From` alone are explicitly untrusted.
2. Requires exact `reply+{lowercase UUID}@mail.empire-ai.co.uk` recipient, trusted MTA queue ID, unique well-formed RFC `Message-ID` and `In-Reply-To`, and bounded CRLF header area.
3. Requires independently owner-supplied, authenticated MTA evidence callback that provides a matching raw-message digest, source queue ID, trusted local-peer provenance, trusted source auth result `dmarc_aligned_pass`, and receive time within five minutes of signing. A caller-supplied `Authentication-Results: dmarc=pass` header **cannot** substitute.
4. Requires independently owner-supplied canonical tenant/intent binding. A reply alias is not by itself consent, tenant assignment, or buyer identity.
5. Requires an atomic, durable event-reservation callback before signature. The optional `ProtectedIngressReplayStore` implements file-based O_EXCL no-follow reservations in a pre-provisioned owner-only 0700 directory with 0600 records, fsync and replay refusal. No original email, body, contact, sender, recipient, private signing key or raw RFC data are saved by that store.
6. Requires a separately injected Ed25519 private signer and strict pinned key identity. No automatic key creation/loading, environment secret fallback, public HTTP API, SMTP listener, webhook, sender, database writer, key export or timer exists.
7. Produces a private, domain-separated signed transport observation compatible with the **existing Wave 10 JEV verifier**. The envelope contains sensitive RFC/tenant references and MUST remain within a protected owner-controlled repository; only Wave 10's HMAC-obscured review packet is safe for the Founder dashboard.

`scripts/probe_owned_ingress_receipt_chain.py` provides only an explicitly invoked **synthetic fixture smoke**:
- makes an ephemeral test Ed25519 key held in process memory;
- creates a fictional original inbound RFC message and fake owned-IMAP thread;
- runs bounded owner callbacks and a real durable filesystem replay reservation in a temporary isolated directory;
- verifies the signed statement with Wave 10's independent pinned public key;
- proves duplicate issuance is refused;
- emits only a privacy-safe Boolean/status packet and destroys the temporary store.
- Default without `--fixture-smoke`: zero network, zero keys, zero mail or database I/O.

Tests:
- `tests/test_owned_ingress_receipt_producer.py` covers real cryptographic and end-to-end JEV verifier roundtrip, duplicate envelope, fake Authentication-Results, mismatch in original content digest, invalid recipient, invalid queue, duplicate/missing RFC headers, source and canonical tenant failures, bounded payload, signer absence, symlink/world-readable replay directories, real O_EXCL private reservations and cross-instance replay refusal.
- `tests/test_probe_owned_ingress_receipt_chain.py` verifies the one-shot offline gauntlet, default inactive mode, no PII/credentials in operator status and truthful Founder API status.
- Existing Wave 9/10 mailbox, canonical CRM, JEV and SQL isolation suites remain intact.

No actual first-party receiving MTA was installed or activated by the test suite.

**Final independent verification:** the full bounded JEV/CRM/Conversation OS/mailbox/research suite returned **765 passed, 10 subtests passed, 0 failures** with one existing AnyIO/Starlette dependency warning. Frontend TypeScript `tsc --noEmit --incremental false` passed, as did Python source compilation and Git diff checks. The one-shot synthetic fixture reported `OFFLINE_END_TO_END_PASS`, with a verified Ed25519 round-trip, verified durable replay refusal, zero network calls, and zero mail/DNS/database mutations.

## Mandatory owner work for an actual receiving service

Do not use a custom Python public SMTP listener in production. Prefer an audited, first-party **self-hosted Postfix MTA** as the receiver with an independent trusted authentication filter and a private, controlled delivery/spool boundary. This preserves vendor independence without hand-implementing the SMTP protocol.

Official references:
- https://www.postfix.org/postconf.5.html
- https://www.postfix.org/virtual.5.html
- https://www.postfix.org/ADDRESS_CLASS_README.html

Separate acceptance requirements:
1. Proven host ownership, inbound TCP/25 reachable and non-blocked, reverse DNS reputation, correct A/AAAA and MX plan, TLS certificates, SPF/DKIM verification, correctly trusted DMARC alignment at receipt and an observable post-queue origin.
2. `smtpd_relay_restrictions` must reject unauthorised destinations (`reject_unauth_destination`), recipient maps must recognise only valid and provisioned reply UUID aliases; **no open relay, catch-all or wildcard recipient acceptance**. Review local/virtual/relay address classes per Postfix documentation; never infer domain ownership from a wildcard.
3. The authoritative SMTP MTA must evaluate sender authentication, not accept an `Authentication-Results` MIME header supplied by a remote sender. Account for forwarding, replay, SPF envelope identity vs header From and aligned DKIM. Unauthenticated/ambiguous items must be quarantined for review, not attributed to an authenticated buyer.
4. Queue/spool must be durable, privilege-separated, malware/attachment bounded, safely recoverable, with backups, authenticated local owner IPC, explicit privacy retention and a plan for failed deliveries. The signer must not be a network-accessible endpoint; it must live under a separate mail-owner OS identity and prove original MTA event custody.
5. Callback `trusted_mta_evidence` MUST be an independently audited MTA-log adapter bound to the authenticated post-queue peer, raw-message hash, verified DMARC result and queue ID; its `authenticated_local_peer=True` claim is only useful when actually secured. Never allow generic JSON/CLI input to assert the trusted state.
6. Callback `canonical_intent_binding` must use the existing privileged EmpireDB tenant/contact owner with scoped permission and suppression checks. The current synthetic binding is NOT suitable for production. The signed envelope is not a customer identity or consent certificate.
7. Provision owner-restricted signer keys and a durable replay/custody log with auditable revocation/rotation. Review the protected replay store's privilege boundary and crash recovery as part of the receiving-MTA security audit before deployment.
8. Staged receiving test against a dedicated, explicitly approved subdomain or other isolated route before live MX cutover. Preserve current SES/Resend destination until independently verified alternate delivery and rollback, to avoid losing legitimate inbound replies. No automated cutover follows from this handoff.
9. Founder authorisation required separately for installing the mail server, modifying DNS/MX, provisioning signing keys, attaching commercial CRM mappings, applying migration 051, and any outbound or payment actions.

## Independent truth and next milestone

Offline end-to-end pipeline success means the **functionality can produce and cryptographically verify a bounded signed first-party delivery observation** when the external MTA/canonical evidence is genuinely trustworthy. It does NOT prove that EmpireOS has begun receiving mail, that Postfix/DMARC is installed, that the source authenticator is audited, that a genuine buyer replied, that contact permission is clear, or that a payment occurred.

Founder status now exposes: synthetic ingress receipt pipeline tested=TRUE; sovereign MTA deployed=FALSE; production signer audited=FALSE; actual first-party inbound verified=FALSE.

This wave completes the reusable, zero-cost offline receipt producer, atomic replay guard and end-to-end proof. Production receiving infrastructure and genuine commercial outcome proof remain explicit operational release gates.
