# Commercial Funnel Truth Continuity V1

Diagram: outbound intent → canonical original reply → closer case → buyer org / prospect / opportunity
→ [persisted closer qualification event] independently of
[order → installed terms review → approval event → optional acceptance event]
→ existing read-only performance records → independent deduplicated stage counts.
The existing order → verified outcome / payment / recognized revenue path remains separate.

Contract / owners:
A/B: conversation_qualification produces advisory signals only. Qualification is
persisted by the governed advance_closer_case producer as a closer_events
state_advanced event with payload.state=qualified, actor and decision note.
Read contract requires that event and its explicit canonical case/reply bindings;
case state alone or recommendation rows do not qualify. No new store is needed.
C/D: buyer_commercial_terms_intake extracts literal buyer-stated prices;
commercial_terms_materializer proposes reviews only. decide_commercial_terms
persists an approved review and approval event, installing identical terms,
review ID/hash/actor/time/price on the order. record_commercial_acceptance adds
buyer evidence and acceptance event. Approved coherent installed terms count;
accepted terms must also have coherent persisted acceptance evidence.
Proposed, draft, rejected, expired and unknown terms do not count.
E: closer_cases.outbound_intent_id / reply_id / fulfilment_order_id plus actual
participant IDs and buyer.org_id provide attribution. Conversations are checked
when explicitly linked, never inferred. V2C lineage is preserved and checked
where present; middle stages never require or imply a revenue outcome.

Worker assignment: Codex extends existing owners and canonical read boundaries.
Independent critique: source diff, model/proposal truth checks, mismatch matrix,
deduplication, temporal checks, database read-only enforcement and authority audit.
Live verification excluded by CODE + TEST ONLY. No persistence writes or migrations.

## Implementation, critique and verification

Root cause of qualification gap: advisory transcript-signal review was the only
qualification projection consumed by outreach; closer's persisted qualification
transition history was never projected into the snapshot. The read contract now
requires one canonical closer_events state_advanced/qualified decision, nonempty
actor and rationale, a canonical original reply, coherent case progression, and
explicit case/participant/tenant bindings. A current qualified case flag alone,
positive/question/objection/later label, recommendation or model confidence is
insufficient. qualified_at and canonical event/reply refs are retained.

Root cause of terms gap: the snapshot never read commercial_terms_reviews,
commercial_terms_events or the approved terms installed in the canonical order.
The read contract requires an approved review, a unique matching approval event,
identical installed review ID/hash/terms/price/actor/decision time, and compatible
order progression. USD/USDT/BSC and any embedded terms price must agree with the
existing canonical producer's contract. Accepted terms additionally require the
matching acceptance event, evidence kind/reference, actor and time. Terms success
is APPROVED or ACCEPTED; it never means payment or recognized revenue.
PROPOSED/REJECTED/explicit EXPIRED/UNKNOWN diagnostic states do not count.
The existing review schema supports pending/approved/rejected, not a separate
REVIEWED status. Explicit expiry, when supplied in persisted terms, fails closed.

The existing repository shares identity checks between middle and terminal
bridges. Qualification can exist before an order; terms can exist without
qualification or a verified economic outcome. Missing explicit linkage yields
UNKNOWN without reconstructed evidence. Existing V2C provenance is checked against
persisted completed work where present; absent refs remain unknown. Terminal
verified outcome validation is unchanged and remains the only economic truth gate.
Middle-stage validators run again at the optimizer boundary. Counts deduplicate
canonical qualification event refs and terms review refs, independently of outcome
ref deduplication. Source availability no longer means every record has a stage;
record-level missing evidence remains UNKNOWN.

Critique fixes: supplied reply/case/conversation IDs cannot override persisted
identity; terms-event payloads cannot contradict participant IDs; failed revenue
reads cannot overwrite valid middle-stage buyer/opportunity bindings; future,
synthetic, advisory, model-inferred and forecast-derived stage evidence is rejected;
qualification must agree with persisted case progression; approval/acceptance must
agree with order progression; terms content cannot contradict approved economics.
Advisory review and existing proposal/intake workers were not repurposed into
commercial authorities. No new ledger/store/event bus/migration was introduced.

Verification: 83 new focused cases plus 418 existing cases = 501 tests passed
(493 in the final required regression run plus 8 direct conversation regressions).
Outreach V2, verified runtime bridge, V2B/V2C, closer, terms/intake/readiness,
repository/provider/transaction and outbound authority regressions passed.
Five changed Python owners compile. git diff --check passes.

Unverified: six additional conversation API tests remain unverified. The unchanged
test_api_qualification_is_read_only_and_non_executing was isolated with a 20-second
process timeout and stalled inside FastAPI TestClient. No production logic or API
source was weakened to bypass it. The eight direct qualification/timeline tests
passed. No live database, embedded database integration or production smoke was run.

Read-only proof: producer still uses the existing read_only_snapshot lease;
provider is byte-identical to task start. The existing bridge regression tests
prove mutation/RPC rejection, no commits, rollback/close, and rejection of partial
SQL reads. New refresh tests exercise stage observations with fake gateways that
reject writes and RPCs. The learning path calls query and pure projection helpers
only; it does not call materializer execution, advance/propose/approve/accept RPCs,
prepare orders, initiate payments, or recognize revenue.

Task-start SHA comparison preserves all unrelated dirty work. Optimizer function
AST comparison changes only build_performance_snapshot; arm selection, minimums
(8 per arm / 16 per segment), 20% exploration and winner safeguards are unchanged.
Closer execution producer, terms intake, database provider, governors and reply
suppression remain unchanged. No score grants authority; stage execution_authority
and snapshot execution_authority stay none. Branch remains agent/data-cloud-wave4;
no staging, commit, reset, clean or switch occurred. No production send/write,
service/timer restart, migration apply, payment action or authority expansion.
Migration 018 still has SHA256
e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21.

Remaining gaps: legacy qualification decisions without explicit rationale,
ambiguous/missing bindings, incomplete approvals/acceptances, or missing V2C work
remain unknown. Stored actor/rationale and canonical producer records are retained;
no model interpretation of a rationale establishes business need. Live evidence
coverage, role provenance, reader privileges, query volume at scale and genuine
live traversal have not been verified. No claim of production funnel completion.

COMMERCIAL FUNNEL TRUTH CONTINUITY V1 = PROVEN OFFLINE / CODE LEVEL.
