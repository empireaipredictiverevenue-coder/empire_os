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


## Reddit / LinkedIn intent integration — evidence-only

The existing 15-minute `empire-community-intent.timer` observes public Reddit RSS
and public LinkedIn search results (via Search Fabric). The hourly revenue
intent observer and the intent brain can process those observations, while the
existing Buyer Scout accepts only business URLs explicitly present as evidence.

The **same** `scripts/reconcile_buyer_email_relationships.py --write` now
attaches `social_intent_review` to the existing private commercial relationship
registry. No second CRM, collector, timer, Gmail sender, or contact table.

- Read-only inputs: `runtime/acquisition/signal_inbox.json`,
  `runtime/community_intent/latest.json`, and
  `runtime/buyer_acquisition/linkedin_revenue_department_latest.json`.
- Review records are bounded to 8 Reddit plus 8 LinkedIn evidence links,
  deduplicated by public post URL, with an observation-age limit.
- Company candidates require an **explicit external business website URL**
  matching a canonical company identity already known to the registry.
  A social post link or similarity of company names does **not** identify
  the author or prove a purchasing role.
- Even an explicit website link is only a **potential citation match**, not
  authenticated employer/owner identity, demonstrated buying intent,
  permission to contact, or consent.
- The underlying signal score is a research-ranking heuristic; it does not
  grant buying authority, checkout readiness, campaign permission or spend.
- Observe the live `source_status` field: Search Fabric's LinkedIn retrieval
  can fail independently of the consumer code; an old search result returned
  today does not prove the post was published today. The review explicitly
  marks publication dates as independently **unverified**.
- LinkedIn Revenue Department account intelligence is distinct from public
  LinkedIn posts; an observed decision-maker, verified contact and authorized
  outreach must be checked independently.
- On source absence or invalid JSON, the social review says UNAVAILABLE
  without disabling the existing warm-buyer email and launch workflows.
  Nothing sends, posts, connects, buys traffic, or changes search indexing.

**9 October 2026 observation:** the durable signal inbox held 29 unresolved
Reddit and 100 unresolved LinkedIn rows. Only one Reddit row had any
external evidence website URL, and there were **zero** exact first-party website
matches to the commercial registry. The most recent LinkedIn search returned
a provider failure; Reddit RSS returned HTTP 200 but no accepted observations
in that one query. The separate LinkedIn department had 9 candidates, zero
verified contacts and zero candidates ready for human outreach review.
This identifies **research backlog**, not 129 potential paying customers.

The next actionable work is improving verifiable public first-party business
identity and resolving the LinkedIn Search Fabric retrieval failure. Neither
is a reason to authorise cold outreach from anonymous social posts.
