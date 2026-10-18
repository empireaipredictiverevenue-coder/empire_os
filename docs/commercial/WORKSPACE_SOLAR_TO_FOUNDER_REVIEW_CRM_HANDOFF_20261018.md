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
The new frontend release was **activated successfully by the founder** and independently verified live. The read-only Founder API had already been reloaded, and the existing five-minute worker is active; no additional timer or outbound authority was introduced.

## Private Founder reply-triage release — verified live

The founder ran the approved private release successfully. Independent service inspection confirmed the active console uses the new isolated reply-triage build and preserves all eight existing routes at HTTP 200. The live Founder Mail page contains the six-company Gmail panel. The Founder API, CRM pilot and five-minute Gmail tracker remain active. The read-only API reported six verified sent messages, zero incoming candidates, zero new CRM conversations and no outbound send. The public Founder Mail URL remained 404. The prior service configuration is preserved for rollback.

The Gmail-to-Founder review interface is deployed. Actual Gmail-to-CRM promotion still requires a genuine inbound message, exact contact and canonical-intent linkage, tenant authority and suppression review.

## 18 October night — six-thread canonical intent existence reconciliation

New **read-only** `empire_os/workspace_solar_canonical_intent_review.py`
uses only the existing `empire_closer_observer` role and previously
configured systemd `founder_reply_reader_dsn` credential. It runs ONE
parameterised, time-bounded READ ONLY transaction (exact six Gmail thread
IDs, original intended recipients, original provider sent-message IDs)
against `public.outbound_intents`. The SQL returns count aggregates only,
not addresses, IDs, bodies, terms or message content to Python or HTTP.

New private loopback GET endpoint:
`/v1/founder-mailbox/workspace-solar-canonical-intent-review`.

The endpoint distinguishes a missing **visible** canonical Gmail-thread
record, a thread/recipient disagreement, multiple exact-recipient sent
intents, missing canonical approval evidence, an unbound provider
original-sent message ID, and a structurally matching review candidate.
It explicitly NEVER establishes tenant authority, signed sender identity,
suppression clearance, commercial buyer interest, authorised CRM promotion
or recognised revenue. A zero means `not visible to this restricted
reader`, NOT `proved absent globally`. A reader/SQL/access failure is an
HTTP 503, not a false zero.

Tests are isolated using a fake least-privilege database transport:
no live SQL mutation, OAuth, sender, CRM service or secret changed.
The new route reuses the existing Founder read API and requires only that
service's ordinary read-only reload; no migration, new credential, new
timer, CRM write, payment or public publication is part of this change.

**Independently verified production result (18 October 2026):** the new private read API returned HTTP 200 with six complete aggregate rows. For GB NRG, Perfect Sense Energy, Solar4Good, Sustain Commercial Solar, SOL PV Group and 100% Renewables, the restricted canonical observer saw **zero matching Gmail-thread intents** and zero exact-recipient sent intents. Separately, the authenticated Workspace Gmail API verified all six real original sent messages and zero reply candidates. This is a **historical send-to-canonical-ledger mapping gap**, not a failed Gmail send and not proof that no canonical record exists outside this reader's visibility. No DB or CRM record was inserted.

The canonical review now supplies a deterministic `next_founder_review_action` for each of the six exact thread anchors, with `historical_send_reconciliation_automatically_authorized=false`. Where no canonical intent is visible, the action is `REVIEW_HISTORICAL_SENT_EVIDENCE_FOR_CANONICAL_ADMISSION`. Ambiguous/mismatched or partially proved intents instead receive specific review steps. This does not authorise an automatic retrospective approval, new send, tenant binding, contact creation or suppression change.

## 18 October follow-up — second canonical join, exact original recipient

The initial canonical SQL used an exact Gmail thread metadata key, and
therefore its zero rows alone could not prove that no original-recipient
canonical records were visible. The same existing restricted read-only
reader now executes a SECOND bounded, parameterised aggregate in the
same read-only transaction, joining outbound intents by the six exact
original recipient addresses *without* requiring Gmail metadata. It
returns aggregate counts only: all visible recipient intents, sent
recipient intents, sent recipient intents with approvals, and those
carrying the exact original provider message ID.

The two result sets are both required to be complete, six-thread
consistent, and internally bounded before returning evidence; partial
or contradictory results fail closed (HTTP 503). Matching a recipient
alone never authenticates the originally sent Gmail message, grants a
tenant relationship, resurrects historical approvals or permits a send.
If exact-recipient records exist without thread metadata, the next
action is `REVIEW_POTENTIAL_UNLINKED_EXACT_RECIPIENT_RECORDS`, NOT an
automatic link. Restricted-reader zero remains
`NO_RECORD_VISIBLE_TO_READER`, not a database-wide absence claim.

The dedicated Founder API/systemd reader and existing credential were
reused. No OAuth, backend timer, role, schema, CRM or payment mutation.
Live outcome recorded after independent endpoint readback.

## 18 October late — historical Gmail receipts prepared for canonical admission

The exact-six provider evidence import path is now **implemented and
committed**, detailed in
`docs/commercial/WORKSPACE_SOLAR_HISTORICAL_SENT_RECEIPTS_RELEASE_20261018.md`.
Live Gmail and restricted EmpireDB checks confirmed six original sent
messages and **zero** matching thread/recipient canonical intents visible
to the restricted reader. No second send is needed or authorised.

The append-only private manifest, sourced from the provider-verified
snapshot, contains six hashed/replay-checked original sent receipts and is
held `0600` at
`runtime/buyer_network_intelligence/workspace_solar_historical_evidence_20261018.json`.
The private custody write and repeat verification PASS. Existing timers,
Founder UI and CRM service remain untouched.

Migration
`migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql`
and importer
`scripts/import_workspace_historical_sent_receipts_20261018.py`
are **STAGED ONLY**, tested and committed. Neither was activated against
production EmpireDB; explicit founder/DBA approval is needed for that
database mutation. The historical evidence table is deliberately
separate from `public.outbound_intents` and always marks receipts
`UNBOUND_EXTERNAL_SENT_OBSERVED`. It cannot fabricate campaign
approvals, CRM contact authority, signed buyer responses or revenue.
No new role, secret or scheduled service is introduced.

The staged import verifies every stored receipt field against a fresh
provider-derived receipt, rejects duplicates/conflicts and requires a
root-to-postgres peer-auth privilege drop for its explicit operator-only
branch. No new CRM opportunity will be created by this import. After a
real reply arrives, the existing privacy-minimal Founder review still
needs original sender, suppression, canonical intent, contact and tenant
authority to justify CRM promotion. **Do not implement another Gmail
monitor or replay the six original outreach emails.**

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
