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

## 18 October addition — RFC reply-chain evidence, no CRM promotion

The existing `empire_os/workspace_solar_reply_tracking.py` now evaluates the
original SENT message's RFC `Message-ID` against a candidate's RFC
`In-Reply-To` and `References` headers in the same authenticated, existing
Gmail metadata scan. It does not make new API calls or retrieve message bodies.
The private snapshot and founder review projection retain only ONE enum:
`DIRECT_PARENT_MATCH`, `ORIGINAL_MESSAGE_REFERENCED_ONLY`, or `NOT_PROVEN`.
They never persist raw RFC IDs, addresses, subject text or Gmail message bodies.
A missing/invalid header is `NOT_PROVEN`, not a fabricated parent match;
duplicate identity/RFC headers hold the entire scan.

Direct parent match is stronger **thread ancestry**, not a signed proof of
identity, authorised tenant access, commercial intent or a sale. All such
authority flags remain FALSE. The existing scheduled five-minute worker
automatically collects this header-level evidence when a genuine candidate
first appears. Old stored candidate snapshots lacking the additional optional
enum are compatible with the fail-closed founder reviewer and original
deduplication logic. Scoped runtime and simulated reply tests passed.

The clean committed-code Founder Mail Next.js release was also built in
`/home/ubuntu/empire_worktrees/empire_founder_mail_clean_release_20261018`
from commit `65b7b50f` with **zero tracked/untracked changes** and completed
a successful Next.js 16 Webpack production build. The clean release lacks
other agents' still-uncommitted Founder routes. It has therefore NOT replaced
the live `empire-founder-console.service`; its deployment remains under
coordinated owner review. No company website or auth deployment was made.

## Later 18 October — exact Workspace recipient routing review

The same bounded read-only metadata scan now additionally labels **candidate**
messages with `EXPECTED_WORKSPACE_TO` or `RECIPIENT_ROUTE_UNVERIFIED`
based only on a strict, bounded match of the original `To` header against
the three already-known first-party Workspace routes:
`phil@empire-ai.co.uk`, `phil@mail.empire-ai.co.uk` and
`reply@mail.empire-ai.co.uk`.

It never copies raw routing addresses from an incoming header into the
private snapshot or public-facing evidence. The Founder review projection
accepts only those two states, treating older snapshots without the optional
field as unverified. A suspicious or indirect To address **does not cause a
candidate to disappear**; it remains a founder review item with an explicit
routing gap. A matching To does NOT prove delivery, actual sender identity,
consent, buyer interest or CRM tenant authority. The original six sent
Gmail anchor IDs remain unchanged, and the monitor creates no CRM rows.

59 related tests passed including RFC reply chains, unusual To values,
malformed routing, old-snapshot compatibility, provider IDs and no-send/no-DB
invariants. A new authenticated live scan still read all six original
outbound messages and found no inbound header candidates. The refreshed
snapshot and existing timer need no new scheduled service.

The clean isolated Founder Mail release cannot safely replace the current
live release yet: a live route parity check confirmed that the running
console already serves `/founder/youtube` and `/founder/intent-review`,
while the clean committed-code build lacks those other agents' additions.
The production frontend remains untouched, with no silent feature rollback.

The already-approved privileged canonical CRM sales intake aggregate is
NOT an exact Gmail-to-prospect lookup; it cannot be used to claim these six
sent messages are CRM records. An attempted remote invocation of the
separately privileged aggregate observer was denied by the command
interface, and no permission or credential workaround was used.

## Founder Mail UI production completion — 18 October

The founder ran the already-tested private Founder Console release command
and the operator reported `PRIVATE_FOUNDER_MAIL_RELEASE_VERIFIED`.
Independent loopback tests proved the Gmail review panel LIVE under
`/founder/mail` on the private Founder Console (port 3001), with all eight
prior routes still HTTP 200 including YouTube and Intent Review. The
existing Gmail reader snapshot still had six verified sent anchors and zero
incoming candidate messages. No canonical CRM identity, contact, lead,
tenant or revenue event was created from these observations.

The live Founder Console uses the frozen isolated parity candidate release,
not the shared dirty Next.js working-tree build. Public
`https://empire-ai.co.uk/founder/mail` still returns HTTP 404.
Production source/deployment details:
`docs/commercial/FOUNDER_MAIL_WORKSPACE_SOLAR_UI_RELEASE_20261018.md`.

**Completed gap:** authenticated Gmail metadata → bounded private snapshot →
read-only founder review API → rendered Founder Mail page.

**Still unverified:** actual inbound response and its exact authorised
canonical sent-intent / contact / tenant CRM join, followed by a founder
review before prospect promotion.

## 18 October evening — exact-contact reply triage, UI candidate built

**Next gap closed in source:** the same existing authenticated Workspace
reader also labels a candidate as `EXACT_ORIGINAL_RECIPIENT` or
`SAME_DOMAIN_DIFFERENT_ADDRESS`. This is compared to the frozen exact
recipient of the six original sent messages; it does NOT retain or expose
the incoming personal address. Exact From equality is not proof of email
authentication, human identity, consent or CRM tenant authority. Older
snapshots without the field are shown as unverified; all six original
message anchors and five-minute polling cadence are unchanged.

The Founder API now carries a deterministic read-only `next_review_step`:
only exact From + direct RFC parent + expected Workspace To can suggest
checking canonical outbound intent, tenant, suppression and message
content. Any incomplete match requires sender/thread/routing review first.
**Both cases remain human review only** and explicitly have
`crm_handoff_authorized=false`, `contact_identity_verified=false`,
`commercial_intent_verified=false`, `crm_conversation_created=false`.
No automatic contact, prospect, conversation, send or payment is created.

The existing Founder Mail panel source was enhanced to show those flags
and next-review steps only if a real Gmail candidate appears. It displays
zero candidates honestly otherwise. Full app ESLint + TypeScript checks
passed, and the new production Next.js 16 Webpack build at
`/home/ubuntu/empire_worktrees/empire_founder_mail_reply_triage_candidate_20261018`
passed. The isolated port 3099 preview preserved HTTP 200 on all eight
current Founder routes, including YouTube and Intent Review. The source
snapshot differs from the LIVE private prior release **only** in the
single `workspace-solar-review.tsx` component; no other agents' work is
replaced.

Operator-gated rollback-safe script:
`scripts/deploy_private_founder_mail_reply_triage_20261018.sh`.
Preflight passed against the previous live service and its exact
`70-private-solar-review-release.conf` drop-in. An approved root-run
incremental release would create only
`80-private-reply-triage-release.conf` and restart the existing private
Founder Console, returning to the previous 70 drop-in on failure.
The new frontend release is **NOT yet live** until the operator applies it
and a live HTTP readback proves the new working directory. Backend rollout
requires only a read-only Founder API restart; the five-minute worker
launches fresh Python code on its next existing run.

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
