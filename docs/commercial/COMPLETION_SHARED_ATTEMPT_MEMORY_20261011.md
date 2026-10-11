# EmpireOS — shared completion task memory / no-repeat preflight

**Date:** 11 October 2026
**Goal:** Stop reassigning the same work across Astra, the department queue, Hermes, Pi and Empire Coder when evidence already records an attempt, a verified feature, or a known builder-capacity failure.

## Reuse existing system

The existing Empire Coder `ContextMemory` persists context **per coding task**. The existing `runtime/execution_plane/completion_checkpoints/` stores full-completion checkpoints. The existing `completion_board_dispatcher`, `DepartmentWorkQueue`, `execution_plane_dispatcher` and `completion_reconciliation` remain the authoritative scheduling/verification routes.

The gap was **cross-task and cross-agent attempt memory**: a new worker could be given the same checklist item with a new request ID without reading the prior blocked Hermes outcome or a feature commit that was tested but not deployed.

This change extends the current checkpoint store with immutable `task_memory_attempt_...` receipts; the actual prefix is `task_memory_attempt_<hash>.json`. No database table, new memory server, vector store, agent, service, scheduler, provider, execution mode or timer is introduced.

## Receipt and task identity

- The stable task key is a SHA256 digest of the canonical checklist **section + exact task text**, whitespace normalised. It survives line-number insertions without conflating distinct tasks. The old `check_<hash>` line-bound ID remains accepted only for its exact original line/content. Renames or conflicts fail closed.
- Each receipt has a deterministic attempt ID, exact canonical task, owner, stage, immutable evidence references, optional Git commit, specific non-sensitive blocker, date, source-checklist hash and explicit `execution_authority: none`.
- `CODE_VERIFIED_NOT_LIVE` requires an actual commit in EmpireOS Git, a matching `commit:` evidence ref, a `pytest:` ref, and a feature-branch ref. It **does not establish real-world outcome or production deployment**.
- `PROVIDER_CAPACITY_BLOCKED` records exact provider evidence and a bounded known blocker; it does not imply the requested feature itself failed code verification.
- `REVIEW_REQUIRED` retains an exact unresolved blocker. `RESOLVED_WITH_NEW_EVIDENCE` must reference the previous held attempt and fresh evidence, but remains a **review gate**, not permission to automatically retry.
- No raw prompts, credentials, recipient addresses, secrets, bearer tokens, arbitrary URLs or other unbounded content are stored. Receipts are 0600, fsync'd and installed through atomic exclusive hard-links after their JSON is fully written. Repeat writes are idempotent; there is no history overwrite.
- Malformed/oversized/forged memory fails closed with `MEMORY_INVALID_HOLD` for new work instead of silently forgetting prior attempts.

## Existing worker integration

1. `completion_board_dispatcher` reads memory before queuing. The original packet ID continues to derive from the full checklist chunk, preventing changed memory from manufacturing duplicate plan IDs. Held tasks are excluded from the **new model task content**; fully held chunks create no new agent job. Each packet exposes `held_item_ids` and exact `checklist_lines` for reconciliation.
2. `department_worker` revalidates the **current** checklist and shared memory on every old `completion_board_live_v3` READY packet **before** budget reservation or model invocation. A held or stale mixed packet blocks as a unit: it is not allowed to replay already-verified or failed tasks accidentally.
3. `execution_plane_dispatcher` calls the same preflight on `checklist:check_<hash>:line_N` and `checklist:task_<hash>:line_N` requests before publishing Hermes jobs or invoking Pi/Empire Coder. An unresolved receipt or merely reviewed unblocking evidence produces `HELD_BY_ATTEMPT_MEMORY` and zero builder action. Non-checklist-scoped actions keep their original behavior.
4. `completion_reconciliation` now shows `CODE_COMPLETE_NOT_LIVE`, `BUILDER_PROVIDER_BLOCKED`, or `REVIEW_PRIOR_ATTEMPT` instead of declaring such tasks DONE. Founder gates remain founder gates.
5. `completion_closure_reconciler` explicitly rejects memory-prefixed files and memory-scoped packets even when altered to claim `LIVE_VERIFY_DONE`. Only independently verified production closure evidence may affect the master checklist.

**Inspect the shared task state:** `/srv/empire_os/.venv/bin/python -m scripts.inspect_completion_task_memory --repo-root /srv/empire_os`. This command performs no writes, external calls or new work.

## Actual October 11 work to preserve

- Item 180: Astra validated-workstream ranking, feature commit `d4599b40`, 299 passed, **code complete, not live**.
- Item 190: Daily Results opportunity evidence, feature commit `eb338c8f`, 281 passed, **code complete, not live**.
- Item 187: Founder Radar lifecycle evidence, feature commit `2a096d9b`, 257 passed, **code complete, not live**. An earlier governed Hermes attempt on the same task failed because no healthy zero-cost model existed; the direct implementation must not be forgotten.
- Item 264: remaining Sensor Mesh to Opportunity Radar, Hermes `completion-20261011-sensor-radar-read-bridge-v1`, **provider blocked; no code or test proof**.
- Item 824: first-party queue/lease/worker OTEL trace chain, Hermes `completion-20261011-otel-queue-trace-v1`, **provider blocked; no code or test proof**.

The failed provider message was: `HermesControlError: OmniRoute has no healthy eligible zero-cost Hermes model candidates`. A single first-party local structured-patch fallback generated **no independently verified proposal**; the loopback local model probe timed out. No further blind retry or paid provider activation is justified by that evidence.

## Scope and activation

At the engineering checkpoint, the canonical on-server checklist parsed **875 total, 594 checked, 281 pending**. Previous chat counts of 285 were from an older snapshot and must not overwrite current production truth. Check the live checklist again on each future cycle.

Implementation and tests live on the isolated `feature/completion-shared-attempt-memory-20261011` branch based on `2a096d9b`. Do not claim it has changed production agent behavior until the existing governed release is merged and read back. Recording immutable **non-consequential** checkpoint evidence is distinct from deploying code.

Do not mutate the checklist, merge into production, send outbound, restart services, migrate EmpireDB, launch paid traffic, accept terms, move funds, recognise revenue or enable new agent/model runtimes through task memory.

## Completion/retry discipline

Before any new checklist-scoped job: **read shared memory → inspect specific prior code/tests/blocker → compare with current source → decide whether new evidence exists → route through existing gate**. Missing proof stays PENDING. A repeat PLAN packet is not an IMPLEMENT success. A feature-branch commit is not live activation. Never auto-clear a founder or model-capacity hold by changing a request ID.


## Post-implementation rehearsal: historical plans, not duplicate plans

A production-shaped rehearsal using a separate copy of the current **285 pending** canonical checklist rows, the **five immutable memory receipts**, and the existing department queue uncovered a critical hidden replay defect:

- Original receipt-only release candidate would create **12 new PLAN packets** because changes to checklist line numbers and the item mix reshuffled line-bound packet IDs.
- The existing durable queue actually contains **53 finished department handoffs** from the same canonical completion board. Those are **PLAN-submitted evidence only**, not code implementation or completed business tasks.
- Reading their original exact task text + section + historical line-bound IDs recovers **288 distinct semantic plan identities**, **281 of which match current pending work**.
- The hardened release candidate recognizes those prior PLAN handoffs by **semantic task identity**, even after line shifts, and refuses to repeat their plans. It still permits genuine first-time scoped IMPLEMENT requests through the existing governed execution plane.
- Second fresh-copy rehearsal: **3 new PLAN packets for only 4 genuinely unplanned items**, no duplicate previously planned tasks, no external actions, no production queue/checklist mutation.
- Existing completion reconciliation on the rehearsal reports **3 CODE_COMPLETE_NOT_LIVE**, **2 BUILDER_PROVIDER_BLOCKED**, **239 PLAN_HANDOFF_ONLY_BUILD_OR_VERIFY_PENDING**, **34 REAL_WORLD_EVIDENCE_REQUIRED**, **6 FOUNDER_GATE**, and **1 NEEDS_WIRING**. All 285 pending tasks remain open until their separate test/live/approval evidence exists. The PLAN handoff state is explicitly not implementation or verification.

The four truly new checklist items identified on 11 October (line numbers at capture, not durable IDs) are all in Sales/Revenue:

- **643:** Obtain one actual buyer-approved PPL form/API or PPC call buy-box, with real buyer, permissible traffic source and commercial eligibility.
- **644:** Implement and independently verify consent-bound homeowner/form enquiry identity and receipts in **sovereign EmpireDB**; do not replace EmpireDB with Supabase or legacy SQLite.
- **645:** Bind each buyer's approved intake schema, deduplication/exclusivity rules, consent evidence and accepted/rejected postbacks/call routing where applicable.
- **646:** Obtain explicit founder go-live approval and independent payable-event, settlement and fulfilment verification; this is a founder gate, never an autonomous launch.

This identifies the real next business work instead of re-planning the other 281 items. Any model-capacity failures remain remembered and do not justify another blind Hermes/Ollama retry. The rehearsals used \`/var/tmp/empire_completion_memory_dispatch_rehearsal_20261011\` and \`/var/tmp/empire_completion_memory_dispatch_rehearsal_fixed_20261011\`. Both are disposable *copies*, not live execution.

**Release remains gated.** The memory receipts are live, but source code must pass production merge/readback before the current Astra/department workers use this guard automatically.

**Final verified regression after semantic handoff repair:** 317 tests passed, one upstream Starlette/anyio deprecation warning, zero failures. A broader suite including SkillForge earlier had a separate existing static-contract failure; that same SkillForge failure was reproduced on the untouched parent branch and was not changed here.
