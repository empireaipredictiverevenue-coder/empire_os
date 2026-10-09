# Buyer commercial workflow — operating contract

Single founder-owned flow:

**First-party discovery → canonical company identity → first-party evidence →
Gmail thread evidence → relationship stage → founder review → governed outreach →
commercial verification → realised revenue.**

## Authoritative boundaries

- The canonical buyer candidate queue remains owned by the existing buyer
  intelligence pipeline. The relationship reconciler **reads** that queue and
  `founder_qualification_actions_latest.json`; it does not rewrite either.
- The Gmail source is `runtime/buyer_network_intelligence/
  gmail_relationship_evidence_latest.json`, a private (0600) summary of
  **connector-read** threads: entity/alias, thread ID, last sent/received
  message IDs and timestamps, bounced business addresses and typed next-action
  code. No raw message bodies, attachments or mailbox credentials.
- Multiple business domains can belong to a single company only with explicit
  aliases grounded in the inspected correspondence (e.g. LeadBank/AllianceVS
  and Validated/Home Services Lead Group). Conflicting aliases fail closed.
- Output `commercial_relationship_registry_latest.json` is private (0600).
  It unifies all current candidate companies, Gmail threads and founder holds.
  Stable status categories: inbound-review, awaiting buyer, contacted,
  contact-delivery hold, commercial evidence hold and research-only.
- The **existing** buyer-acquisition scout (30-minute timer) runs bounded
  evidence checks and this reconciliation. No extra server timer.
- This is **not** outbound authority: all source and output documents say no
  send, no automatic contractual acceptance, no payment/routing and no
  suppression clearance. A request to send still needs a live suppression
  check, contact authority, exact recipient and founder approval.

## Mailbox ingestion limitation

Gmail is connected to ChatGPT, **not** to the EmpireOS server. The initial
Gmail thread metadata snapshot was imported from the connected account using
the Gmail connector; the server's owned IMAP service currently reports
`CONFIGURATION_REQUIRED`. Reconciliation of the last imported snapshot is
automated, but **fresh Gmail collection is not** yet autonomously proven on
EmpireOS. Never label a snapshot a live inbox feed.

The connector import must refresh its metadata snapshot on new replies, or
an independently authenticated first-party mailbox adapter must be
configured and verified before marking ongoing Gmail ingestion autonomous.
Snapshots over 96 hours old are clearly flagged stale; no "no new reply"
claim or send decision can rely on stale evidence.

## Safety and completion criteria

- Zero duplicate company rows from multiple threads or aliases.
- Delivery failures apply to the exact failed email address, not a blanket
  rejection of a company with another valid human contact.
- Manual and due-diligence holds override any engagement or scoring.
- New inbound message IDs are detected idempotently; unchanged snapshots
  never produce repeated "new response" events.
- Audit labels distinguish an observed reply from an approved buyer,
  contracting terms, payout, billable calls and realised revenue.
- No software change or green unit test authorises outbound or traffic.
- Evidence stage and relationship registry both pass the main regression
  suite and a live OBSERVE read-back before declaring complete.
