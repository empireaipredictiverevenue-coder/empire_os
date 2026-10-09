# Empire AI — Parallel Buyer Activation, 10 October 2026

**Goal:** Move **LeadBank, Validated and Connexis** toward the same level
of commercial and technical evidence as Lead Smart, without repeating Lead
Smart's setup, numbers, pricing or route. One existing commercial registry,
one existing buyer scout, no additional scheduler or platform.

## Verified partner engagement and proposed pilot

| Partner | Correspondence proof | Current verified state | First proposed pilot (not buyer-approved) |
|---|---|---|---|
| LeadBank / AllianceVS | Eleonora's 8 Oct onboarding request, `gmail:1a11902593b62d2c`; founder's response `gmail:1a11aa2fa91135f0` | Named onboarding handoff; requested campaigns/ZIPs; agreements, MVA and W-8 come next | US roofing install/replacement, Empire-owned SEO inbound calls, one buyer-selected ZIP corridor |
| Validated / Home Services Lead Group | Zach's 7 Oct reply `gmail:1a114d6b9b33e40b`; founder's reply `gmail:1a117d5a0e0fb530` | Buyer has described publisher source/compliance conditions and revenue share, but not live roofing buy-box | US roofing install/replacement, first-party organic call traffic, one source-approved corridor |
| Connexis | Kieran's 28 Sep reply `gmail:1a0e6d76dbe29583`; founder's follow-up `gmail:1a10922d0223f192` | Kieran promised programme details; none received | Choose one current UK or US buyer campaign for first-party organic calls |

**Three review-only threaded Gmail drafts saved on 10 Oct** in the original
threads. No sends: LeadBank `1a0cfb65e0dd960e` to Eleonora (Alina CC);
Validated `1a0cfb667dca0957` to Zach; Connexis `1a0d9fa5b944630a`
to Kieran. Founder approval/suppression checks remain required before sends.
The drafts exist in connected `flavag83@gmail.com`; the professional mailbox
has not been independently configured on EmpireOS.

## Reuse Lead Smart's *process*, never another partner's contract

1. **Commercial** — actual buyer campaign and permitted source, geography,
   job categories, homeowner criteria, chargeable event, cap, hours, duplicate
   and disputes, payout basis and settlement, recorded against the partner's
   exact email or signed terms. No guessed ZIPs, payouts or conversion.
2. **Legal/compliance** — founder review of agreement/MVA/W-8 or programme
   terms, consent and landing-page requirements. Use the existing EmpireOS
   Documenso deal-room signing workflow *only after explicit approval*.
3. **Partner-specific digital inventory** — derive a separate, review-only
   landing/creative packet from our existing roofing design, with distinct
   partner copy and source attribution. No new live landing route and no
   co-mingled supplier attribution before approval.
4. **Technical** — source-bound tracking ID/number, distinct partner-specific
   route, confirmed caller-ID/consent/ZIP restrictions where required,
   authenticated read-only source and buyer route evidence, controlled
   nonbillable test only if authorised.
5. **Controlled traffic** — buyer-approved corridor and hours, founder
   explicit launch authority, one bounded pilot, no third-party publisher
   inventory or paid traffic.
6. **Realised economic memory** — independently reconcile buyer accepted
   call/lead, payable qualification, actual settlement and fulfilment;
   never claim revenue from a landing review, test call or proposed payout.

## Current gate matrix (OBSERVE; not approval)

| Gate | LeadBank | Validated | Connexis |
|---|---|---|---|
| Two-way correspondence | Observed | Observed | Observed |
| Buy-box/coverage/qualification | **Waiting** | **Waiting** | **Waiting** |
| Buyer source approval | Unverified | Unverified | Unverified |
| Payout, disputes, settlement | Unverified | Unverified | Unverified |
| Contract/compliance signoff | Unverified | Unverified | Unverified |
| Partner-specific landing signoff | Unverified | Unverified | Unverified |
| Tracking number/campaign binding | Not configured | Not configured | Not configured |
| Runtime routing evidence | Not configured | Not configured | Not configured |
| Founder traffic approval | Not granted | Not granted | Not granted |

These gates are materialized as
`partner_pilot_readiness_queue` within the existing private
`runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json`.
The existing 30-minute buyer scout refreshes relationship/readiness state
from its **last imported** Gmail summary; it cannot automatically infer a
buy-box or a signed agreement from email metadata.

## Parallel next actions and ownership

**Commercial agent (safe):** Once approved, send the saved draft within each
original thread. Parse any genuine buyer reply into a human-reviewable
requirements matrix and preserve exact Gmail evidence. Do not re-send
identical requests to partners. Prioritize LeadBank's onboarding handoff,
then Validated's first-party supply review, then Connexis' selection of one
live market.

**Technical agent (safe now):** Inventory reusable landing, ZIP gate,
tracking, call-route observer and revenue-attribution components. Prepare
strictly isolated partner configuration proposals; do not create live routes,
purchase numbers, substitute Lead Smart IDs or assume Ringba is the approved
provider for the other partners.

**Legal/ops agent (on response):** Review buyer-specific source,
consent, disclosures, W-8/MVA and service-level terms; preserve sign-off
evidence and use the existing Documenso path, never sign automatically.

**Founder approval gates:** Any external send, contract signature, traffic
activation, third-party costs, or binding commercial terms. A draft in
Gmail is not a send approval.

**External dependencies:** A partner must provide an active buyer buy-box,
source approval, pricing and technical specification. We cannot truthfully
complete these gates on their behalf. Product and routing activation is
strictly postponed until these facts exist.

## Completion standard

**Partner onboarding ready:** verified buy-box + legal terms + isolated
landing and tracking proof + buyer-approved traffic source + accepted
controlled pilot plan. **Live revenue proven:** genuine qualified billable
event plus independently verified payment/settlement and fulfilment.
Do not mark a company as onboarded because an email reply or code test passed.


## 10 October — LeadBank has advanced to onboarding preparation

Exact Gmail response `1a1230003eb39320` in existing thread
`1a0cfb65e0dd960e`, dated **2026-10-09T23:29:13Z**, was received
after the three founder-authorized partnership follow-ups. Eleonora explicitly
stated that she **will send** the agreement and onboarding form and has
forwarded technical questions to Mahad, then offered a call.

**Document receipt: not yet evidenced.** Technical answers, buyer
ZIP-level coverage, payable event, approved traffic source, routing method,
payout, executed agreement and live supply authorisation are all still
unverified. No call required to accept this pending email handoff.

The existing private
`runtime/buyer_network_intelligence/gmail_relationship_evidence_latest.json`
was updated using the exact Gmail message ID and timestamp, retaining all 57
prior thread records and preserving the original global mailbox capture time.
The existing registry now categorizes LeadBank as `INBOUND_REVIEW_REQUIRED`.
No extra outreach was sent after this reply.

### Reusable preactivation packets, never Lead Smart clones

The existing `partner_pilot_readiness_queue` now includes a nested,
partner-identified `technical_review_packet` for each of LeadBank,
Validated and Connexis. Each contains:

- Proposed first-party organic supply and review-only landing namespace.
- Null-valued provider IDs, buyer ZIPs, payout/settlement, eligibility,
  approved disclosures, signed agreement, tracking number and destination.
- Explicit booleans blocking caller-ID, routing, landing publication,
  signing, traffic and revenue.
- Evidence lineage for a human-reviewed promise, only when its exact
  current Gmail inbound message matches the stored source ID.
- An independent `current_next_partner_task`; no field is populated
  with another partner's number, offer, payout or route.

**LeadBank next:** review Eleonora's agreement and onboarding form on
receipt; then parse Mahad's actual technical specification. A promised
document is not a received, reviewed or signed document.

**Validated next:** await Zach's accepted geography and qualification
terms before preparing a partner-specific landing and route for review.

**Connexis next:** choose a named live UK or US programme from Kieran's
confirmed buy-box before selecting postcode geography or integration.

Automatic refresh is through the existing buyer-scout-to-registry path;
no separate queue/timer/service was introduced. Current technical
review packets grant **zero** of nine launch approvals.
