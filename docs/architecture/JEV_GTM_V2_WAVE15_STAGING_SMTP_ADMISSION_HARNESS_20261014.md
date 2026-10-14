# EmpireOS JEV Wave 15 — Isolated SMTP Admission Implementation

Date: 2026-10-14
Feature worktree: /home/ubuntu/empire_worktrees/jev_gtm_v2_20261014
Previous commit: 9a7d173b
Status: implemented RCPT admission test operator, **not** a live mail receiver.

## What was implemented

scripts/probe_postfix_staging_smtp_rcpt.py:
- Does nothing by default.
- Only when explicitly invoked with --approved-isolated-loopback-rcpt-test, connects to fixed loopback address 127.0.0.1:2525, with a four-second timeout. Never reaches production MX, external DNS, hostnames, or a public SMTP service.
- Verifies the expected mx-stage.mail.empire-ai.co.uk ESMTP greeting and no AUTH/STARTTLS advertisement from the OFFLINE profile; unexpected services fail closed before MAIL or RCPT.
- Tests one synthetic, exact, provisioned reply+UUID fixture recipient for 250/251 admission.
- Requires 550/551/553/554 rejection for bare reply@, different UUID, unlisted local mailbox and external recipient (relay denial). Temporary 4xx responses are HOLD, not success.
- Calls RSET after each test and never calls DATA, even on an allowed recipient. No messages are delivered or queued by this script.
- Reports status, per-case labels/codes, flags for no buyer identity, no original-provider proof, no MX authorization, and no message DATA. No real recipient addresses or bodies are returned.
- A recognized banner is **not independent proof** that the daemon is actually the approved Postfix instance; that still requires owner attestation.

tests/test_postfix_staging_smtp_rcpt_probe.py:
- Synthetic offline SMTP callback fixture exercises all five cases and proves the code issues no DATA.
- Invalid banner, prohibited advertised capabilities, SMTP unavailable, unexpected 250 relay grant, missing fixture alias, 4xx temporary rejection and default/no-network behaviour all fail closed.
- This is an operator harness test against an emulated SMTP response, **not actual Postfix SMTP reception**.

## Independent environment findings

On the connected EmpireOS host, Docker daemon access was denied, and rootless user-namespace creation was denied. Current OS has no installed Postfix service account, postdrop group, Postfix binaries or live TCP/25/2525 SMTP listener. The first-party receiver acceptance cannot be run here without obtaining an independently approved isolated environment.

A separate container available to ChatGPT was assessed, but Debian apt package fetch failed due to DNS/network unavailability; therefore no real Postfix container could be installed or started there.

The existing /srv/empire_os production checkout has substantial concurrent modified/untracked files from other agents. It has not been reset, cleaned, merged or overwritten. The complete JEV worktree remains separately committed and is not yet live in the current production checkout.

## Blockers before production

1. Founder-approved isolated container/VM with actual Postfix 3.10, real service identities and a private loopback listener.
2. Real Postfix postconf/postmap compilation and five-case RCPT behaviour (including external relay denial) with result captured and service identity independently verified.
3. DKIM/SPF/DMARC trust-boundary handling, separate signer custody, original MTA queue/digest provenance, canonical EmpireDB recipient/tenant/contact mapping and replay audit.
4. Delivery, bounce/retry/retention, suppression, rollback and isolated approved inbound test.
5. No MX change until the replacement handles the current live SES/Resend route with tested rollback and original message custody.

No live SMTP daemon installed, no mail sent or received, no runtime service restarted, no database migrations, no DNS changed. A successful synthetic test is not a production release.

## Final engineering test result

Full JEV/CRM/mailbox/Conversation/research/staging regression: **832 tests passed, zero failures, 10 subtests passed, one pre-existing AnyIO/Starlette deprecation warning**. This is a test-harness and synthetic-protocol result, NOT actual Postfix ingress verification.
