# Empire AI — Workspace Reply → Founder Review → Canonical CRM handoff

**18 October 2026 — new founder read-only review path, not canonical CRM intake**

## Verified completed

- Workspace Google OAuth scopes are gmail.send + gmail.readonly. The actual
  primary Gmail account is phil@empire-ai.co.uk; sending From alias remains
  phil@mail.empire-ai.co.uk.
- Six verified emails and exact six Gmail threads are monitored by the
  existing five-minute empire-buyer-acquisition-team.timer. It runs the
  already-existing bounded, metadata-only polling script without a new timer.
- The private authenticated Workspace snapshot at
  runtime/buyer_network_intelligence/workspace_solar_outreach_reply_review_latest.json
  is held at 0600, owned by ubuntu, with no message bodies, subject lines or
  recipient addresses. Data is refreshed by the existing Ubuntu-owned worker.
- NEW projection module empire_os/workspace_solar_founder_review.py validates
  exact six sent-message anchors, source completeness, private permissions,
  freshness (20-minute maximum), anti-replay IDs, original sender context,
  candidate timestamps and false commercial authority. A corrupt or stale
  input becomes an explicit 503, not an empty successful inbox.
- NEW GET /v1/founder-mailbox/workspace-solar-reply-review on the EXISTING
  empire-founder-dashboard-api (loopback-only 127.0.0.1:8766) surfaces
  precisely six business-labelled rows and any original provider **header
  candidates** with Gmail review links. No mail bodies, subjects, addresses,
  automatic send, lead creation, tenant attribution, CRM mutation or revenue.
  A genuine new provider header becomes actionable for HUMAN review in this
  already-existing founder workflow; it is NOT automatically a sale.
- The read projection against actual production snapshot returned six
  verified sent anchors, zero inbound candidate messages, and
  crm_conversation_created=false. This is the HONEST baseline.

## What remains conditional / NOT verified

- A reply candidate requires founder review of actual Gmail message including
  sender/source and content, and suppression/opt-out classification, before
  calling it genuine buyer interest or creating follow-up copy.
- Do not promote a candidacy directly into Revenue CRM. The established
  empire_os/gmail_reply_adapter.py ingest path requires a CANONICAL
  outbound_intent with sent status, exact Gmail thread, normalized recipient,
  and identity evidence. The six externally sent Workspace messages were
  not proved linked to approved canonical outbound_intent/conversation
  records. An arbitrary domain match or original Gmail sent receipt cannot
  supply canonical tenant authority or contact permission.
- The existing tenant-scoped Revenue CRM /reply-qualification-review requires
  a genuinely linked CRM prospect and conversation and its exact tenant
  binding. We have NOT established that for the six outbound messages, so
  no fabricated tenant records or synthetic reply events were created.
- The Omnichannel Design Studio CRM UI has NOT yet consumed this new read feed.
  The new read surface is limited to the existing Founder Read API, rather
  than exposing unbound private source evidence through tenant endpoints.
  UI owner can add a read-only card AFTER confirming founder auth/proxy scope.
- A new real reply and its correct CRM ingest path must be proved in a
  supervised, identity-authorised pilot before marking CRM handoff complete.

## Runtime health checklist

```bash
curl -fsS http://127.0.0.1:8766/health
curl -fsS http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-reply-review
./.venv/bin/python -B -m scripts.poll_workspace_solar_outreach_readonly
```

The GET is private loopback and should not be routed publicly without founder
authentication. The JSON has a safety boundary: every CRM promotion flag false.

**Never** launch a duplicate email service, automatically forward or send
incoming content, manufacture a first-party enquiry, assume a lead buyer,
grant tenant access based on shared company domain, or claim verified revenue
from Gmail metadata alone.
