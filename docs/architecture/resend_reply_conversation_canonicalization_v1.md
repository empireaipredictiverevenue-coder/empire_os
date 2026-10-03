# Resend Reply Conversation Canonicalization V1

## Purpose

Migration 033 closes the revenue-path gap between the governed
Resend inbound reply ledger and canonical Conversation OS.

## Atomic boundary

A verified Resend `email.received` event now enters one
`ingest_outbound_reply` database transaction:

1. resolve the governed outbound intent;
2. insert/reuse `outbound_replies`;
3. preserve suppression state on replay;
4. append `outbound_events.reply_received` idempotently;
5. create/reuse exactly one canonical email conversation for
   `outbound_intent_id`;
6. append/reuse the canonical `email.received` inbound event;
7. return `actual_revenue=false`.

Classification and suppression continue through the existing
governed path.

## Evidence

The webhook computes `payload_sha256` from the exact signed raw
HTTP request bytes after signature verification.

Conversation event evidence records:

- transport provider: `resend`;
- outbound intent ID;
- legacy reply ID;
- provider message ID through `provider_event_id`;
- subject;
- sender;
- `untrusted_content=true`;
- `executable=false`;
- exact raw request SHA-256.

A repeated provider event with a different payload hash fails
closed.

## Identity

Empire thread identity is the canonical `outbound_intent_id`.

External conversation identity:

`resend:outbound-intent:<intent_uuid>`

Canonical Conversation OS provider remains `email`; Resend is
the transport/evidence provider.

## Authority

`empire_reply_ingest` receives only:

- SELECT/INSERT/UPDATE on bounded email conversations;
- SELECT/INSERT on their conversation events.

RLS requires:

- `channel='email'`;
- `outbound_intent_id IS NOT NULL`.

Migration 033 grants no:

- send authority;
- outbound approval;
- commercial-terms approval;
- payment authority;
- fulfilment authority;
- revenue-recognition authority.

## Historical replies

Migration 033 does not fabricate provider hashes for historical
reply records.

Historical canonicalization requires either:

- a genuine signed provider replay whose exact request body can
  be hashed now; or
- a separately governed recovery method using existing verifiable
  evidence without pretending that evidence came from the new
  live webhook path.
