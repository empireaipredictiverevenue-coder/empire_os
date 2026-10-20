# EmpireOS — Verified Coder PLAN-to-IMPLEMENT bottlenecks

20 October 2026. Founder-directed Graphify owner investigation.
No synthetic buyer, revenue, Coder job or approval records were created.
This is a live diagnostic and handoff, not a transfer of ownership.

## Original real sources

- /srv/empire_os/runtime/coder/jobs (original canonical queue)
- /srv/empire_os/runtime/coder/plan_promotion_latest.json
- /srv/empire_os/runtime/founder_directives/records
- /srv/empire_os/empire_os/coder/plan_promotion.py
- /srv/empire_os/empire_os/coder_supervisor.py
- Canonical git status --porcelain

At approximately 12:39 UTC, the canonical queue contained 2,412 original
persisted completed PLAN records. 2,375 had no promotion contract, 37
had structurally complete VERIFY contracts and ZERO had structurally
complete IMPLEMENT contracts. A rolling 24-hour sample had 119 recent
persisted completed plans and no promotion contracts. The latest original
promotion service receipt scanned 160 plans, promoted none and held all.

The Founder Directive store held 16 records: two implementation_ready
with internal_plan authority, 12 implementation_failed and two implemented.
The supervisor checks the shared checkout for nonprotected dirty files:
roughly 193 such paths existed. It will not enqueue a new implementation
while this gate is active. 11/12 historical implementation-failed
directive receipts contained model/provider/inference-related indicators.
Those are sanitized error classes, not a verified provider root cause.

## Three real existing owner actions

1. Coder supervisor owner: reconcile each nonprotected dirty path with
   its true existing owner; do not reset or commit someone else's files.
   Use a clean authorised worktree or the existing execution-plane process,
   with scoped paths/leases. Only then revisit the two genuinely
   implementation-ready directives. Internal_plan is not approval to
   mutate production, send outbound, move money or deploy.

2. Coder plan-promotion owner: obtain explicit, authenticated approved
   execution-plane requests for specific work. A contract needs a genuine
   internal_write authority, exact allowed_paths, lease_resources,
   execution_plane_request_id and real required_tests. The native Coder
   plan_promotion._validate_contract checks field structure, NOT whether
   the authority and execution-plane IDs are authentic. Do not mint
   invented contracts or automatically promote the 2,375 unsupported plans.

3. Coder inference-reliability owner: review privately the original 11
   historical model/provider-indicated failed implementation records.
   Check existing approved provider/fallback configuration without
   duplicating that owner's implementation or broadly retrying mutations.

A real resolution requires at least one genuinely approved IMPLEMENT job
from its existing owner to reach the real apply boundary and record an
original verification result. Graphify's existing prepatch observer can
then report its attested static dependency review. Neither code context
attachment nor PLAN/VERIFY completion alone proves engineering uplift.

## Installed read-only diagnostic

Run the following from the production checkout:

PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B -m scripts.review_graphify_implementation_funnel_20261020 --read-only

New Graphify-owned components:
- empire_os/graphify_implementation_funnel.py
- scripts/review_graphify_implementation_funnel_20261020.py
- tests/test_graphify_implementation_funnel.py

It emits aggregate original counts, structural contract status, founder
directive state, historic failure categories, dirty-checkout count and
precise existing owner action requirements. No source texts, job/task IDs,
private error messages, dirty filenames, commercial records or authority
grants are exported. This is non-atomic read-only observation; the
relevant owner must recheck source evidence immediately before mutation.

The founder wants the bottleneck fixed. This Graphify release improves
visibility and reconciliation; it does NOT claim other owners' gates
have been cleared or fabricate a successful IMPLEMENT outcome.


## Production release checkpoint

- Graphify development commit: ebeef0ede794a2cd593c34451193c8a8c055a2c6
- Production diagnostic commit: f255b5144e19c781948529568b550bc0d6817be0
- Full relevant Graphify/Coder regression suite: 164 passed, one existing
  third-party Starlette/AnyIO deprecation warning.
- Actual production readback: 2,413 persisted PLAN records, 2,376 without
  promotion contracts, 37 structurally complete VERIFY and zero complete
  IMPLEMENT contracts, 193 dirty nonprotected files, two directives
  implementation-ready, 11 historical model/provider-indicated failures.
- Coder worker was not stopped or restarted by this release; its source
  and queue were unchanged. The private 20-module code graph remained
  CURRENT_ATTESTED_CODE, 20/20 fresh source files.
- Exact Graphify-owned source files are clean in production Git, and the
  report can now be rerun without any data mutation.

The ACTUAL implementation blockage is still present. These requirements
must be delivered by the existing Coder supervisor, plan-promotion and
inference-reliability owners. Do not call this a repaired IMPLEMENT funnel
until a genuine authorised implementation reaches an original verified
result; do not issue a fictitious completion receipt.
