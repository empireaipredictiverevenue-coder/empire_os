# EmpireOS — Founder mailbox provider hold in existing Founder Ops

**Date:** 2026-10-15. **Mode:** OBSERVE; no mail delivery or extra infrastructure.

## Production source evidence

The 12:15 UTC department-cycle systemd run stopped in the already-installed
mandatory `run_founder_mailbox_inprocess_observer.py` post-stage. Its
authorised first-party mailbox reader returned the typed error
`HTTPException: 503 mailbox_provider_unavailable:MailboxReadUnavailable`.
This is NOT evidence that there were zero actual inbound replies; it
means the attempt to read the original mailbox source did not succeed.

The observer's normal existing result file
`runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json`
recorded `status=OBSERVER_ERROR`, 0 observed, no outbound, no
mailbox write, no DB write. It must NOT be promoted into
`VERIFIED_RUNTIME` simply to pass a heartbeat.

## Bounded existing-control integration

The existing `empire_os/conversation_control_operational_truth.py`
now reads the above small JSON observer result along with the same
canonical reply-control, collector and linkage snapshots already used.
Only the fixed status enum and timestamp freshness are surfaced in
`conversation_evidence_review` through existing Ops Control and
`/v1/founder-ops/status`.

It deliberately does NOT propagate the free-text provider error,
raw recipient/sender/message IDs, tokens, email bodies or contact
identity. Mailbox `OBSERVER_ERROR` adds the exact typed blocker
`FOUNDER_MAILBOX_READ_UNAVAILABLE`, while missing/stale observer
metadata is separately held. A claimed in-process mailbox verification
is never treated as independent buyer or reply-identity evidence.

## Unresolved operational boundary

This change is diagnostics **only**; the underlying mailbox account's
configuration, Google Workspace/OAuth/IMAP permissions and provider
availability remain unverified. There is NO provider swap, credential
change, service restart, systemd override, or bypass of the existing
mandatory read stage.

To resolve service health safely:
1. Read the existing mail-provider readiness endpoint and first-party
   provider selection WITHOUT printing credentials or email content.
2. Verify supported account identity, OAuth/IMAP read scopes and
   official mailbox provider connectivity; do not use Resend/AWS as
   an accidental fallback.
3. Run a dedicated read-only provider proof with safe bounded metadata,
   then observe the next natural department heartbeat.
4. Only after real original message/thread and canonical entity/tenant
   evidence is available can Conversations & Replies controls advance.
5. Keep all outbound, money and customer actions founder gated.

No new machine, agent, timer, database, commercial execution or
data migration is introduced.
