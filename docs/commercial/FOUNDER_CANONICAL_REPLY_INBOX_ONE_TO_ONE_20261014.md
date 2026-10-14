# Empire AI — Founder reply inbox and governed one-to-one Gmail

**14 October 2026 | engineering release note | OBSERVE, no commercial send**

## Reuse, not reinvention

Existing, verified 13 October infrastructure remains intact:
- The `empireos-workspace-mail-511518` OAuth client and secure `google-workspace-internal-token.json` are the running Gmail sender, not the legacy test-project token.
- A real internal test message from `phil@mail.empire-ai.co.uk` reached a founder-controlled inbox with SPF, DKIM and DMARC passing.
- Separate test messages addressed to `reply@mail.empire-ai.co.uk` and an intent-specific reply address were accepted and their visibility copies delivered. Neither test was a commercial buyer reply.
- The Resend-labelled webhook and Amazon SES inbound MX still serve the currently working receiving route. Do NOT change MX on the assumption it is broken.

## What was engineered

### First-party canonical reply viewer

`empire_os/empiredb_founder_reply_mailbox.py` adds an optional provider inside the existing Founder API (no new process/timer). It reads **only email replies already admitted into canonical EmpireDB** and related sent/replied outbound intent records. This is NOT a complete Gmail/IMAP inbox and cannot discover unrelated personal messages. It uses parameterized, bounded read-only transactions under the existing `empire_closer_observer` role (read grants already present in migration 016). It exposes no database write or send action. Text is a short, untrusted preview. A stored classification is not represented as proof of buyer identity or purchase intent; all suppression and draft-send gates stay closed.

Explicit opt-in configuration is `EMPIRE_FOUNDER_MAILBOX_PROVIDER=empiredb_canonical_replies`; the dedicated least-privilege DSN is `EMPIRE_FOUNDER_REPLY_READER_DSN`. Neither is installed in the current Founder API process. Do not copy write-capable credentials into this service. Its default `owned_imap` provider is unchanged, and the optional Google Workspace direct reader remains consent-gated.

### Existing Gmail sending path, one recipient at a time

`empire_os/outbound_email_transport.py` now offers `GovernedGmailEmailTransport`, wired into the **existing** `execute_governor_decision` claim path. It rejects the ordinary payload `.send` method and requires the original authorised `claim_outbound_send` result; it enforces the exact founder sender, Reply-To and durable internal OAuth token. The underlying `send_with_gmail_api` already constructs governed reply aliases and checks commercial holds, approved footer and a single recipient; delivery must still be recorded against the same canonical intent. Unknown outcomes go to reconciliation.

No new sender process, alternate campaign dispatcher or automatic approval was added. The scheduled `outbound_governor_worker._provider_ready()` remains false; no live automatic sending was activated.

## Gates to operating from the Founder Console

- Obtain a **dedicated read-only EmpireDB connection** able to set the existing `empire_closer_observer` role. A privileged, approved service configuration is required to select the canonical provider; no service was restarted by this change. A reading of the canonical inbox does **not** require additional Google OAuth consent.
- To read the **complete professional Gmail inbox** (including messages outside the canonical outbound loop), the existing Workspace Gmail reader still needs Google mailbox-read consent and authenticated account binding. Neither the durable `gmail.send` token nor the personal Gmail reader grants it. Do not fabricate identity or replace the token without consent.
- To retire the third-party incoming mail provider, establish and independently test a new trusted SMTP/MX acceptance path before changing DNS; no SMTP listener or compatible direct MX destination is currently installed. The working route must be preserved until a cutover is specifically approved.
- Individual one-to-one prospect sends still require an exact verified email address, lawful and appropriate contact route, explicit founder approval of the precise message, a fresh suppression/history check, a valid approved canonical intent and successful provider/reply readiness. Approval must not be inferred from this engineering work, a service's active status or a historical internal test.

**Production truth:** historical internal send and reply forwarding worked; direct canonical reply viewer code and Gmail governor bridge are staged; full professional inbox and sovereign inbound cutover are not live. No recipient mail sent, no DNS mutation, no systemd restart, no secrets disclosed.
