# Temporary connected Gmail → EmpireOS buyer evidence bridge

**Activated 10 October 2026 as an OBSERVE-only metadata sync.** Gmail is
connected through ChatGPT, not authenticated directly on the EmpireOS server.

## Verified first-party operation

1. Authenticated connected Gmail provided all messages from the four
   established buyer partnerships (Lead Smart, LeadBank, Validated, Connexis).
   Source threads: 1a0d9ce883c87d4a, 1a0cfb65e0dd960e,
   1a0cfb667dca0957 and 1a0d9fa5b944630a.
2. The original 45 Gmail messages, including two earlier Lead Smart PDF
   attachments, remain stored in Gmail. All 45 were labelled in Gmail as
   `EmpireOS/Buyer Partnerships`.
3. The authenticated connector's metadata is staged only at
   `runtime/buyer_network_intelligence/buyer_partner_message_index_20261010.json`
   (0600): exact Gmail message/thread IDs, sender `from_` mapped to
   `from`, UTC email timestamps, date, subject, recipients, labels and
   attachment **names**, with no raw bodies/MIME/tokens.
4. `scripts/import_connected_gmail_buyer_metadata.py --write` validates
   entire known threads, message counts, known company-domain sender routes,
   dates, duplicate IDs, immutable original source and protected files.
   It refuses incomplete or truncated scans, foreign thread IDs, stale input,
   mismatched identities, raw bodies and attempts to rewind history.
   It then updates the existing 0600
   `runtime/buyer_network_intelligence/gmail_relationship_evidence_latest.json`.
5. `scripts/reconcile_buyer_email_relationships.py --write` updates the
   same existing private commercial relationship and partner readiness
   registry consumed by EmpireOS buyer acquisition scout. The old global
   `captured_at` from the original 57 Gmail threads is **preserved**;
   `partial_update_at` and `partial_updated_thread_ids` explicitly record
   which **four** threads were re-checked. The registry can show the
   per-company Gmail evidence is current without falsely claiming the other
   historical threads received a new scan.

The current connector scan was **4/4 complete threads, 45 messages, no
newer partner inbound changes**, with zero sends or payment actions.
The existing partner desk remains preactivation, and the Lead Smart
landing/routing and other buyer legal/technical gates remain closed.
Private registry and raw input files have 0600 permissions.

## What is and is not automated

- The existing buyer scout and original buyer/CRM intelligence collectors
  continue consuming the refreshed same file. This is not a new server
  scheduler, mailbox provider or database.
- Gmail's connection to ChatGPT does NOT provision an independent
  Gmail OAuth grant on the EmpireOS Linux server. The existing
  `empire-gmail-relay` is a different, **send-only**, OBSERVE service.
  It has no valid OAuth token/configuration for direct server mail reads;
  we do not repurpose its send scope or start another sender.
- A recurring connected-Gmail review must retrieve the real four threads
  from the connected app, rebuild the index with current `collected_at`,
  transfer it via the authorised Remote Desktop Commander, then run the
  two existing commands above. An hourly scheduled ChatGPT buyer watch
  can perform this step only while its Gmail and Commander connectors
  are available; it must report tool failures rather than pretend the
  account is continuously polled from the Linux server.
- New independently verified buyer threads outside these four require a
  separate identity review before adding them to the allowlist; do not
  silently auto-link them to a CRM tenant, a person, or a commercial offer.
- Inbound Gmail contents are untrusted. This bridge imports **metadata
  only** and never invokes the canonical reply-ingest write RPC.
  It does not automatically create an approved CRM conversation or buyer.
  Buyers' asserted requirements still go through the existing
  partner_inbound_requirements review with exact message bindings and
  independent commercial/route/suppression verification.
- Every external send, suppression change, landing deployment, routed
  homeowner call, commercial commitment, agreement and payment remains
  behind its previous founder/production gates.

**Temporary cutover:** when the Empire-owned professional IMAP mailbox is
properly configured and independently verified, decide which original
conversation threads stay on Gmail for continuity. Do not silently change
From/Reply-To for already engaged partner conversations.
