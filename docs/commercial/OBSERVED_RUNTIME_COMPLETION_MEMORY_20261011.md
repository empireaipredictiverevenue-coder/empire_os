# EmpireOS — one-hit runtime task-evidence memory (11 October 2026)

**Intent:** stop all agents and founder task reports from treating the three already-running first-party features as "code not live" or reimplementing them. Do not reopen Lead Smart, CRM, paid traffic, outbound or other already owned work.

**Existing architecture:** use `empire_os.completion_task_memory` immutable checkpoint receipts under `runtime/execution_plane/completion_checkpoints`; existing `completion_reconciliation`; existing `completion_task_monitor`; existing `empire-department-cycle.timer`. No new database, agent, scheduler, mailbox, public service, credential, CRM restart or external provider. The three original tested-code receipts and five historic total remain immutable.

## Observed evidence, not invented closure

The new `empire_os.completion_runtime_evidence.observe_existing_runtime` is a bounded **one-time read-only admission verifier** scoped to the exact three outstanding Master Checklist tasks (lines **180, 187, 190** at original capture). It reads canonical local JSON files with strict time, schema, authority, source count and SHA256 checks and, for API-delivered features, probes **only** the existing loopback Founder API `127.0.0.1:8766`, no proxy, no redirect, four-second timeout.

1. **Astra ranking (line 180):** canonical Evidence Router carries same-generation, OBSERVE-only Opportunity History; current Astra Executive carries `empire.astra.validated_workstream_ranking.v1`, `RANKED_FROM_CURRENT_DERIVED_VALIDATION`, ordered after the Router; no commercial or external authority. **Zero real validated candidates is an accepted observation, not an invented success or payable buyer.**
2. **Founder Radar lifecycle (line 187):** live resident HTTP 200 `/v1/founder-dashboard/overview` returns `CURRENT_DERIVED_HISTORY_OBSERVED`; exact router time, count, stage counts, new identity and stage transition numbers match the canonical same-cycle Router/History. `commercial_validation_verified=false` and `outreach_authorized=false`.
3. **Founder Daily Results (line 190):** live resident HTTP 200 `/v1/founder-daily-results/latest` exactly matches canonical `runtime/daily_results/latest.json`. It distinguishes *latest cycle only* from *whole-day totals*, disclaims forecast-as-revenue and has no bound independent commercial outcome feed.

A failure or stale/unsafe source **cannot** be admitted; no synthetic validation, seller approval, signed contract, payment, settled call or realised revenue is inferred. All checks must remain within six hours of this bounded verification.

## Durable, idempotent stage

After code-verified receipt exists, and only after live sources are rechecked, an explicit one-shot command appends the immutable memory receipt `RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE`:

`/srv/empire_os/.venv/bin/python -m scripts.capture_existing_runtime_evidence --repo-root /srv/empire_os --apply`

Without `--apply`, this script is a read-only preview. Source evidence includes content hashes, the preceding tested-feature commit and exact previous attempt ID, preserving the chain. A second invocation recognises captured tasks and **does not submit another attempt, rerun agents or alter any code**.

The shared memory guard still blocks additional build/PLAN dispatch for those tasks. Existing `completion_reconciliation` and `completion_task_monitor` report the new stage `RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE` with next step **"exact independent live-closeout checkpoint and checklist verification; do not rebuild"**. All pending task IDs and other task states remain stable. No expiry-based "not live" flip due to a momentary API/server race.

**Critical closure distinction:** `live_verified=false` on these memory receipts, `stage=TASK_MEMORY_EVENT` (not `LIVE_VERIFY_DONE`). The canonical `completion_closure_reconciler` explicitly ignores these receipts even if tampered. The Master Checklist and its actual authority/approval gates remain untouched. Formal VERIFIED_DONE requires the separate exact row-bound repo VERIFY + independent LIVE_VERIFY_DONE evidence. The runtime proof is real technical observability, not such a closure token.

## Release gate

Isolated development checkout: `/var/tmp/empire_observed_runtime_task_reconciliation_20261011`, branch `feature/observed-runtime-task-reconciliation-20261011`, based on source head `03f125e2`.

- Preview of **all three** features using actual production Router, Astra, Daily Results, and resident Founder API passed without any runtime/checklist/queue writes.
- Focused negative and regression tests: **93 passed**, with one dependency deprecation warning; expected zero failures.
- Wider integration suite: **478 passed** across 34 existing/new test modules, one Starlette/anyio deprecation warning. This suite preceded one additional idempotency test; the final focused suite of **93 passed** after that test was added. Preserve the 146 dirty/untracked files belonging to other agents.
- After merge, perform one exact-readback capture, then reuse existing `refresh_completion_reconciliation` and `refresh_completion_task_monitor` for task-state transition. Do **not** start another agent cycle, the Opportunity Loop, or the Founder API.

**Founder intent:** keep work moving with memory, no repeated engineering loops or Lead Smart re-evaluation.
