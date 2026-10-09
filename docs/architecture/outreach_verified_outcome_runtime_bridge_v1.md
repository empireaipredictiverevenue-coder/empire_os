# Outreach Verified Outcome Runtime Bridge V1

Diagram:
outbound intent → closer case (outbound_intent_id) → original reply (intent_id)
→ case fulfilment_order_id → order prospect/buyer/opportunity
→ buyer org_id + canonical causal_lineage + completed department work
→ existing verified_outcome_feedback reader/builder → existing validator
→ enriched adaptive performance record → outcome_ref deduplication.

Architecture contract: the existing snapshot producer calls the canonical
repository under a read-only snapshot. No name/email/time/similarity attribution.
Missing, ambiguous or contradictory identities fail closed for downstream credit.
Conversation rows, when present, are checked against their explicit intent and
participant bindings; no conversation is inferred. Existing V2B/V2C readers own
payment, independent outcomes, recognized revenue and completed-work truth.
Worker assignment: Codex implements the bounded read bridge and offline tests.
Independent verify: mismatch matrix, existing V2B/V2C/closer/repository regressions,
source diff and authority verification. Live verify excluded by task scope.

Root cause: scripts/refresh_adaptive_outreach_optimizer.py._records selects only
intent delivery, reply classification and adaptive metadata. It supplies no
explicit case/order linkage and never invokes the verified outcome reader.

Qualified conversation remains unavailable: conversation_qualification.py emits
operator-review signals, not a verified stage event causally bound to an outreach
intent/order. Commercial terms remain unavailable: closer parses/proposes terms,
but the snapshot has no canonical verified stage projection with that attribution.
Case state and order state are not substituted for either stage.

## Implementation and verification record

The producer now calls ExecutionBusDataRepository.outreach_performance_records
under EmpireDbProvider.read_only_snapshot. The snapshot uses one repeatable-read,
read-only session, rejects mutation/RPC methods, never commits, and rejects a
swallowed SQL failure before publishing derived data. Database read failures abort
refresh; missing/contradictory lineage yields UNKNOWN without downstream feedback.
The intake is bounded at 10,000 records and a 60-second read deadline; reaching
the record limit aborts instead of claiming complete learning from a truncation.

outreach_verified_outcome_record checks canonical intent/adaptive metadata, a
unique closer case, original reply, prospect, buyer org, opportunity, order and
any existing explicitly bound conversation. It requires identical, executed,
causally eligible lineage on the intent and order. The existing
verified_outcome_feedback reader validates persisted completed work, canonical
outcome, approved payment/escrow evidence and recognized revenue, using the
existing build_verified_feedback_from_records implementation. The existing
validate_verified_feedback gate runs at enrichment and again in the optimizer.
PostgreSQL native UUID/timestamp values are normalized with unwrap_data_value
at the verified-feedback boundary, without changing general provider output.

Returned records preserve tenant_id, outbound_intent_id, prospect_id, buyer_id,
opportunity_id, fulfilment_order_id, outcome_ref, prediction_ref, decision_ref,
execution_ref and verified_outcome_feedback, with explicit attribution evidence.
No fuzzy matching, new economic memory, event bus or revenue engine is added.
The adaptive optimizer remains byte-identical to the task-start version, including
canonical outcome_ref deduplication, 8 deliveries per arm, 16 per segment, 20%
exploration, winner safeguards and no execution authority from learning scores.

Completed offline runs: 395 required/related tests plus 8 direct qualification
and timeline regressions = 403 passed (72 new bridge cases, 331 existing cases).
Changed Python modules compile; git diff --check passes.
Six additional conversation API tests are unverified: an extended run stalled
at test_api_qualification_is_read_only_and_non_executing; an isolated group timed
out at the same untouched FastAPI TestClient test. A separate direct/API mix
also timed out at test_unbound_reader_fails_closed. API timeout cause remains
unknown; the pure evidence-review tests were rerun successfully. No API source
was changed to work around this unrelated limitation.

Task-start hash comparison confirms all pre-existing dirty files are unchanged
except the two requested repository/provider owners. AST comparison confirms
existing provider methods are unchanged and the only pre-existing repository
method changed is verified_outcome_feedback (native-value normalization).
Branch remains agent/data-cloud-wave4. No staging, switching, reset or clean.
No live database connection, production write/send, migration apply, service or
timer restart, grant or authority expansion occurred. Tests use fake gateways,
fake connections and temporary fixture directories. Migration 018 retains SHA256
 e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21.

Remaining gaps: qualified_conversation and commercial_terms stay explicitly
unavailable; their verified, outreach-attributed stage producer is absent from
this snapshot path. Legacy rows without explicit case/order/work lineage receive
no credit. Live schema availability, reader privileges, query volume at scale and
real downstream outcome traversal have not been verified; no grants or migrations
were added to fill those gaps.

OUTREACH VERIFIED OUTCOME RUNTIME BRIDGE V1 = PROVEN OFFLINE / CODE LEVEL.
Production revenue learning remains unproven until a genuine canonical outcome
traverses this live path.
