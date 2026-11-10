# Empire AI — Dots / Manus-style Chief of Staff continuity (10 Nov 2026)

## Authority and ownership
- Owner of executive coordination: **existing Chief of Staff**, per `docs/CHIEF_OF_STAFF_OPERATING_SYSTEM.md`.
- Execution/orchestration owner: existing **ASTRA / EmpireOS**, not this adapter.
- Browser/computer operator owner: original **Empire browser operator / JEV**, not this adapter.
- Existing AgentOS owner branch: `/home/ubuntu/empire_worktrees/hermes_oracle_founder_overlay_20261030`; its original `empire_os/agent_os_*\` memory, founder auth and gateway remain owned there.
- Founder directive source: `runtime/founder_directives/latest.json`, not the adapter's checkpoint.
- Scope of this branch: new, isolated `empire_os/chief_of_staff_continuity.py` + tests + this handoff only. No competing daemon, service, API, private memory store, agent bus, database, or scheduler.

## Verified implemention
- Read canonical existing Founder Directive index and existing ASTRA review; fail closed on malformed/stale/prohibited evidence.
- Preserve existing statuses, priorities, categories, source references and approval gates.
- Rank at most three open items and make next action explicit, while marking actual owner **to verify** rather than inventing assignments.
- Optional `run_tick(repo_root)` persists an OBSERVE-only derived checkpoint to `runtime/chief_of_staff/continuity_latest.json` with an exclusive local lock and atomic restricted-permissions write.
- First tick establishes baseline. Later tick compares statuses, suppresses repeats, captures up to 3 changed attention items. It does not send notifications, delegate work, or trigger provider calls.
- CLI: `python -m empire_os.chief_of_staff_continuity --repo-root /srv/empire_os` for nonmutating evidence check; `--tick` for a single persistent observation cycle, **not** a continuous worker.

## Real, non-simulated preflight (10 Nov 2026)
- Read the existing `/srv/empire_os/runtime/founder_directives/latest.json` and ASTRA snapshot, no production writes.
- Canonical directive count: 23; last-index window: 20 active entries.
- First three action types in this window: RETURN_FAILED_IMPLEMENTATION_TO_EXISTING_OWNER (revenue, revenue, search). This is owner follow-up, **not completion**.
- ASTRA executive overlay status: EVIDENCE_HOLD; no provider send / deployment / revenue authority granted.
- Isolated automated tests confirm baseline, deltas, dedupe, founder gate, stale/corrupt input holds, symlinks, atomic checkpoint and no erasure on invalid evidence.

## Original video feature intake
- User video `https://youtu.be/czYheMQ0Jss`: "The New Way to Make Money with AI at Night (Even If You Have a 9-5)".
- Retrieved transcript themes: autonomous nightly business-opportunity research; market demand and competition/blue-ocean scoring; target clients and willingness to pay; morning ranked HTML report; sales and content execution.
- Empire adaptation: use existing Opportunity Radar + Search Fabric to **verify actual buyers and demand**, Smart CRM for relationship truth, MediaOS for content and owner-controlled approval, and AgentOS/G-Brain for continuity. Do not turn video anecdotes into verified Empire revenue or market prices.
- Commercial north star is **first real customer / recorded sales**, not unlimited side-hustle ideas.

## Exact integration to original owner (not performed by this branch)
1. Existing Chief of Staff / ASTRA owner reviews this adapter and chooses integration point in the already-running department-cycle owner, without new timer.
2. Original AgentOS owner exposes the derived review through existing founder-authenticated read-only API and G-Brain memory route (no public access or duplicated memory).
3. Original JEV/browser operator owner adds a tightly scoped **research-only** operation to investigate *current* qualified demand and produce source-linked dossiers. Internal reversible work may be autonomous only where explicit owner-controlled authority permits.
4. No live outreach, sends, publishing, financial execution, admin changes, deployment/restart or authority expansion from this handoff. Existing human approvals remain enforced.
5. Prove one actual closed-loop cycle: new source evidence -> owner-specific autonomous research -> verified artefact -> status transition -> founder brief with genuine buyer outcomes. No fabricated demonstration counts.

## 10 Nov live read-only recheck of existing JEV browser owner
- Current browser-owner worktree: `/home/ubuntu/empire_worktrees/empire_browser_operator_20261021`.
- Original three selected Node tests: **2 pass, 1 fails**, not proof that all three features are broken.
- Root cause of original test failure: hardcoded `127.0.0.1:3217` currently serves the separately owned SEO Revenue Leakage Design Preview; JEV's `jev_brain_task.test.cjs` expects the synthetic storefront at that address.
- Isolated test using the **original session_task.cjs**, the browser owner's intended fixture on `127.0.0.1:3299`, and *temp-file-only* updated assertions matched current `HELD_REPEATED_FAILED_ACTION` (one executed action rather than the prior `HELD_NO_PROGRESS` two-actions contract). **1/1** pass on that adapted fixture; verified visible click, repeated failed action hold and same-origin page navigation. Existing SEO preview and browser owner files were not changed.
- Browser-owner follow-up: make fixture port self-contained or dynamic, update outdated assertions in the original test, run full original suite and verify runtime/authentication separately before live autonomy. No assumption that a fixture pass validates arbitrary real websites, 24/7 browser access or external actions.

## Status
**BUILT + ISOLATED TESTED** on scoped feature branch; **NOT MERGED / NOT RUNNING AS LIVE 24/7 AGENT**. The existing AgentOS remains the sole orchestration/UX owner.
