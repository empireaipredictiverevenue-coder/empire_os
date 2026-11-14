# ASTRA continuity and operations recovery — scoped architecture delta

Date: 14 November 2026
Status: TESTED SOURCE CANDIDATE; NOT ACTIVATED AS A GUARDED PRODUCTION RELEASE
Owner: ASTRA Executive / existing DepartmentWorkQueue and DepartmentWorker.

Purpose: prevent repeated executive plans from multiplying identical unresolved
department jobs; preserve work identity, tenant and evidence provenance;
aggregate the existing incidents by root cause and accountable department;
restore the existing Ops Sentinel status adapter and prevent green health
claims when any source is stale, missing or unknown.

Canonical placement: no new queue, worker, timer, source of truth or service.
DepartmentWorkQueue is the single durable job owner. ASTRA dispatcher dedupes
only same-invariant tasks for up to 30 minutes; the evaluator preserves a
carryover link to the original queue work. DepartmentWorker's Ops Sentinel
reuses the existing Predictive Cloud status command.

Authority and failure: observe/internal allowed only under original dispatch
contract; no paid source, public publishing, outbound, infrastructure restart,
commercial recognition, migration or self-authorisation. Unhealthy component
evidence blocks completion; missing evidence never becomes health.

Verification: focused regression covering exact cross-plan identity, changed
evidence isolation, health-fail-close, recovered health and grouped exceptions.
Existing adapter, work queue, worker and ASTRA tests also pass. Full production
acceptance still depends on real source freshness, live service activation,
independent verification and business outcomes.

Rollback: revert this scoped commit in the owned branch and preserve the
canonical work queue; do not overwrite other agents' shared-tree edits.
