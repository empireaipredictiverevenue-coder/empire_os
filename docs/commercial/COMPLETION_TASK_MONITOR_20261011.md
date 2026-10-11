# EmpireOS — existing-cycle task monitoring, 11 October 2026

**User objective:** Watch all canonical remaining tasks, show actual implementation and blockers, spot progress changes, and stop silent repeated PLAN handoffs.

**Change:** Extend the already-installed `empire-department-cycle.timer` / existing `empire_os.department_cycle.run_department_cycle` to read the canonical `completion_reconciliation_latest.json` once after normal reconciliation and materialise `runtime/execution_plane/completion_task_monitor_latest.json`. Read this view through the EXISTING Founder Execution Ledger router at `GET /v1/founder-execution-ledger/task-monitor` (after the founder API is reloaded through its approved service gate), or read immediately using `python -m scripts.task_monitor_status --repo-root /srv/empire_os`. **No new timer, agent, mailbox, database, webhook, paid service or synthetic task engine.**

## Task-level truth and memory

Every canonical pending checklist row is bound to the exact existing reconciliation ID and original line; the stable semantic SHA256 task key survives checklist line insertions. All reconciliation rows are checked for uniqueness, one-to-one coverage, state-count consistency and no live execution/checklist-mutation authority. Monitoring only proceeds when the existing reconciliation is OBSERVE-only and less than 20 minutes old. Unknown, stale, duplicated, conflicting, malformed and future-dated sources FAIL CLOSED without overwriting the previous valid monitor.

Stages are **not automatically advanced**: PLAN handed off is not implementation, CODE_COMPLETE_NOT_LIVE is not deployed, NEEDS_LIVE_PROOF is not payment, FOUNDERS_GATE is not approved and CHECKLIST_DONE is *only* a canonical checkbox assertion, not independent production verification. No new tasks or verification evidence are fabricated.

The first monitoring cycle creates a **baseline**, not 281 new completions. Each later cycle keeps the first-monitor date, state-since timestamp, monitored-cycle count and a bounded history of genuine state transitions (max 120). A stage unchanged for 24 hours gains an `NO_OBSERVED_STAGE_CHANGE_24H` attention signal, clearly distinct from any contractual deadline or business failure. Missing/renamed tasks cannot vanish as if completed: only an exact canonical checked-DONE row allows a closure event. Attention ranks actual failed verifications and provider holds first, then code waiting on live proof, founder gates and actionable stale work.

The monitor snapshot exposes per-task state, department, last observed stage change, verification-job reference, memory-commit ID, exact blocker, next evidence step, and attention reason. The existing Founder API provides department/state filters and max 200 rows per request; stale/unsafe reports are unavailable, not shown as live counts. The local CLI prints the top 10 attention tasks and recent transitions. It performs no writes.

## Production-shaped read-only acceptance (before merge)

The existing production reconciliation, checklist and shared attempt memory were inspected **read-only**:

- **281** canonical pending tasks, **594** explicitly checked DONE.
- **198** need live proof, **44** PLAN handed off but not implemented, **31** need real-world evidence, **3** tested code not live, **3** founder gates, and **2** model-capacity blocked builders.
- **8 immediate attention items** (3 code-not-live + 3 founder gates + 2 provider blocked); other pending tasks are reported but do not receive invented deadlines.
- **0 fake new transitions** during the first baseline cycle and **0 external execution authority**.

## Release/activation constraints

Feature branch: `feature/existing-department-task-monitor-20261011`, based on production `fb8fa656`. A guarded fast-forward/cherry-pick is allowed only after independent tests and checking all other writers' uncommitted files. Monitor refresh is a bounded local observation write, not a restart or new timer. The existing founder-dashboard service is **not restarted without explicit authorised approval**: its newly authored API path is not live until its own sanctioned reload. Monitor data can nevertheless be read through the existing CLI and current department heartbeat once the code is merged.

No permission for outbound, traffic, buyer approval, provider switches, schema migration, payment, model invocation or automatic checklist closure is conferred by this monitor. Existing internal agent work continues under all original gates. The monitor does not use email notifications; only the founder status view surfaces attention until a separate, explicitly approved notification policy is specified.
