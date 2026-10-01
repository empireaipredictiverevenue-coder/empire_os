# Organic Growth corrective wiring

Diagram: existing Radar and Search artifacts → Revenue Distribution validation
→ Traffic Specialist proposal review → organic_growth; existing canonical
conversion artifact → ConversionStageEvidence → review_conversion_system
(ConversionStageReview / ConversionSpecialistReview) → organic_growth.

Owner: Revenue Distribution, Phase 5 foundation under OBSERVE. Codex owns this
bounded implementation; focused regression tests provide verification. No new
subsystem, runtime producer, database read, service, or execution authority.
Existing formula predictions are reused unchanged. Unknown economics remain
unknown; zero media spend is not zero total action cost. Acquisition budget
never gates organic review proposals. Snapshot-wide search reviews have no
invented opportunity association.

Interface: additive empire.organic_growth.v1 in the existing latest.json.
Conversion consumes the existing conversion_runtime counts/stages contract;
legacy, stale, malformed or unreferenced observations cannot produce actions.
Serialized conversion proposals and rates are recomputed from canonical counts.
Missing conversion observations remain unknown and produce zero actions.

Authority: proposal only, no publishing/indexation/outbound/paid traffic,
terms/payment/fulfilment/revenue mutation or authority expansion. Only the
existing atomic Revenue Distribution materializer writes its own artifact.
Evidence retains source hashes and opportunity keys; no tenant identity is
invented. No external calls, retries or new scheduling are introduced.

Verification: requested seven test modules, related Search regression tests,
changed-module compilation, diff check, locked formula hashes, artifact readback.
Rollback: remove only this additive projection and review adapter; rebuild the
same artifact. Preserve concurrent work and all source artifacts.

Verified 2026-09-30: 87 focused/adjacent tests passed; all four changed Python
files compiled; git diff --check passed; both formula SHA256 values matched
founder-specified hashes. Existing build_revenue_distribution.py completed.
Artifact readback confirmed organic_growth, both specialists, 23 proposal-only
organic actions, zero conversion actions (stale conversion artifact), and
0 AVAILABLE / 21 UNAVAILABLE opportunity predictions. All required authority
flags remained false/none. Branch and index matched pre-change state. No staging,
commit, service restart, external action, or unrelated materialization occurred.
Checklist: corrective wiring and safe artifact verification complete.
