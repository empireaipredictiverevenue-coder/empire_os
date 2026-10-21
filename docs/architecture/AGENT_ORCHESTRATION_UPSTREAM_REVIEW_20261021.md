# EmpireOS — agent orchestration upstream evaluation (21 Oct 2026)

## Scope and evidence boundary

Independent **OBSERVE-only** review against the current EmpireOS source. The
repository remains authoritative; no new agent scheduler, timer, service,
connection, DB migration, outbound, model runtime, credential or payment flow
was created. Never execute untrusted upstream install/setup scripts in the
production host environment. Clones are **static review copies**, not deployed
runtime dependencies. An upstream README claim is not a validated feature.

Production reference: `/srv/empire_os` branch `agent/data-cloud-wave4`,
commit `782f53022` at inspection. Its working tree contained pre-existing
modifications owned by other work; **none were edited by this evaluation**.

Evaluation branch: `feature/agent-orchestration-evaluation-20261021`
Evaluation worktree: `/home/ubuntu/empire_worktrees/agent_orchestration_evaluation_20261021`
Static upstream checkout location: `/home/ubuntu/empire_upstream_reviews/agent_orchestration_20261021`

## Pinned external review sources

| Review project | Source | Full pinned commit | License anchor | Category |
| --- | --- | --- | --- | --- |
| Paperclip | https://github.com/paperclipai/paperclip | `92cfd701c39bb1ea394a796023481a21decb2532` | MIT | Goals, org hierarchy, skills, budgets, cross-provider agents |
| Orcha | https://github.com/open-orcha/orcha | `e5f9add77ebc6b9e1ecfd8adad04f3c89e42595f` | MIT | Engineering-agent verification, wake and context restoration |
| Nora | https://github.com/solomon2773/nora | `ae7e46e4aff429f88016cd7348eb514cb6d89bd4` | Apache 2.0 | OpenClaw/Hermes fleet lifecycle, telemetry, budget caps |
| head-of-ai-template | https://github.com/doneyli/head-of-ai-template | `c5f7eb6ed38396209260636e71af03e742175122` | MIT | DICE task prioritisation, scope checks (candidate only) |
| template-agent | https://github.com/redhat-data-and-ai/template-agent | `43554147435141948ed2385d8ce054a6842cecdd` | Apache 2.0 | LangGraph orchestration, MCP auth, tracing (candidate only) |

**User clarification still needed to confirm the exact "AI template repo."**
The last two are relevant *provisional candidates*, not an assertion of identity.

Pin verification only says the checked-out commit matches this evaluation's
manifest; it does not verify upstream provenance, release signatures, security,
suitability, dependencies or licenses beyond their apparent files.

## EmpireOS existing authority and capabilities — verified source paths

- `empire_os/department_work_queue.py`: persistent deduplicated queue,
  deterministic IDs, `READY/RUNNING/REVIEW/DONE/BLOCKED/FAILED`,
  atomic leases, stale-worker recovery and `goal_key`.
- `empire_os/department_budget_ledger.py`: worker cost/budget reservation.
- `empire_os/department_worker.py`: authority-preserving worker execution,
  model budget checks, bounded invocation, guarded evidence.
- `empire_os/department_cycle.py`: existing scheduled department heartbeats.
- `empire_os/agent_execution_plane.py`: existing explicit worker kinds,
  routing/authority validation; consequential actions rejected.
- `empire_os/skillforge.py`: review-only catalogue; digest-pinned, explicitly
  approved skills only (do not conflate candidate with executable).
- `apps/search-command-centre/src/app/founder/page.tsx`: existing Founder UI.

These are **source and currently configured service observations**, not proof
that individual live agents have completed a specific task successfully.

## Integration decisions — what not to rebuild

1. **Do not replace EmpireDB** with Paperclip's persistence, Orcha's SQLite or
   template-agent's separate Postgres stack. EmpireDB is the canonical DB.
2. **Do not create another scheduler**: augment the present department cycle
   and execution plane only after a measured gap is established.
3. **Do not auto-import vendor skills** into SkillForge. Third-party text is
   untrusted and remains review-only until provenance, licensing, independent
   holdouts, owner decision and exact digest approval are verified.
4. **Do not let vendor approvals become EmpireOS authorization**: a status in
   another tool cannot approve external messages, paid traffic, fund movement,
   live deployment, irreversible infrastructure or legal commitments.
5. **Do not run vendor agents within the production environment** or expose
   existing founder sessions, credentials and tenant records to vendor code
   for the purpose of this review.

## Specific upstream capabilities worth isolated evaluation

### A. Paperclip: work visibility and goal lineage (priority 1)

Potential value: trace `goal_key -> department work -> review -> evidence ->
realised outcome` and show departmental blockers from a single authenticated
Founder Console surface. Its org/task/budget/skills UX is attractive, but
EmpireOS already has corresponding authorities. Start with **a read-only
comparative UX/product contract**; do not install Paperclip to run parallel
agencies or give it EmpireDB write rights.

Acceptance evidence: one real currently known work item can be reconciled
without losing tenant identity, queue status, authority, failure reason,
source receipt or cost provenance. No optimistic `DONE` from vendor status.

### B. Orcha: wake/recovery and human verification (priority 2)

Potential value: explicit reviewer acknowledgment after verified work, better
idle-agent wake conditions, and bounded agent context after a restart. However
EmpireOS already has stale leases, canonical DONE records and SkillForge
observations. Benchmark **missed/duplicate wakes, recovery time, model token
use and review false positives** against existing baselines before changing
or adding infrastructure.

Acceptance evidence: adversarial resume and duplicate-notification cases;
no agent self-approval, no owner privilege escalation, no second timer, and
consistent canonical evidence at every status transition.

### C. Nora: specialised OpenClaw/Hermes ops (priority 3, conditional)

Potential value: runtime agent lifecycle, monitoring and alerts if EmpireOS
actually starts managing OpenClaw or Hermes fleets. Nora's documented A2A
support is roadmap work rather than a shipped general A2A replacement.
Nora's platform administration, runtime secrets, Docker/Kubernetes access and
local privileged import paths require a separate threat model. Not warranted
as the primary business task manager.

Acceptance evidence: sandboxed demo only, isolated credentials, no Docker
socket exposed to business agents, scoped secret rotation and tenancy tests.

### D. head-of-ai-template: prioritisation scoring (candidate)

Potential value: compare its `(delegability x impact x confidence)/effort`
ranking with EmpireOS's existing priority decisions on a **labelled offline
holdout**. Its dispatch integration is explicitly described as unfinished.
Scope hooks alone are not an adequate security boundary; EmpireOS execution
policy and OS/container restrictions retain authority.

### E. Red Hat template-agent (candidate)

Potential value: enterprise MCP/OAuth patterns, eval harness examples,
tracing and config-as-code. It brings separate Redis, orchestration,
persistence and auth assumptions and is **not** a drop-in replacement for
EmpireOS's controlled tenancy and EmpireDB. Review techniques; do not
launch its infrastructure on the EmpireOS host.

## Production aggregate evidence (read only; no task contents exported)

A one-off Python read of **existing** queue JSON metadata on 21 Oct 2026
reported 3,109 records: 1,679 DONE; 1,202 BLOCKED; 227 FAILED; 1 READY;
0 RUNNING; 0 REVIEW. Every record had a goal_key. Every DONE record included
at least one result_evidence_ref. No duplicate IDs across state folders were
seen and no running expired leases were observed in this snapshot.

Among BLOCKED machine error codes, 864 were
`insufficient_verified_outcome_cohort` and 334 were
`specialist_adapter_required`, with four other cases. These counts do
**not** mean 864 software defects: lack of verified outcome data can be a
necessary governance hold. The 334 specialist cases should be compared
against existing adapters before proposing any implementation. A coarse
keyword classification of FAILED messages yielded 215 source/connection-like,
5 budget/quota-like, 3 timeout/lease-like and 4 other; this is a heuristic,
not proven root cause. No raw private task content or failure messages were
printed.

`empire_os/phase_3f_closeout.py` already contains machine-readable blocker
handling; `empire_os/founder_dashboard.py` already exposes blocked-reason
counts in selected views. **Do not build another duplicate blocker scanner
or Founder Console replacement.** The practical next check is to determine
whether the EXISTING views make verified blocker ownership and remediation
clear, then use the existing canonical paths to fix actual defects.

## Evaluation stages and required proof

**Stage 0 — completed:** Existing control inventory, five source fetches
and immutable manifest pin comparison; seven synthetic audit tests. No
third-party package execution. The source-level audit checks only files and
README feature mentions; never treats them as passing an integration test.

**Stage 1 — next:** Create labelled synthetic tasks and replay real *redacted*
canonical queue outcomes against candidate goal lineage and prioritisation.
Measure quality, duplicate rates, recovery latency, budget effects, evidence
continuity and false approvals. Existing engine is baseline. No task sends.

**Stage 2 — gated:** Inspect import boundaries, licences/dependencies,
secrets, command-injection, prompt-injection, tenant separation, sandbox
isolation, spending and authorization. Obtain owner review for exact proposed
diff before any service activation or restricted DB role grants.

**Stage 3 — only if evidenced improvement:** Minimal add-on inside existing
authenticated Founder Console and EmpireOS routing plane, Canary/OBSERVE
first, feature default off, rollback documented and verified.

## Reproduce the static audit — does not deploy or run source

```bash
WORK=/home/ubuntu/empire_worktrees/agent_orchestration_evaluation_20261021
UP=/home/ubuntu/empire_upstream_reviews/agent_orchestration_20261021
cd "$WORK"
python3 -B scripts/review_agent_orchestration_upstreams_20261021.py \
  --empire-root "$WORK" --upstream-root "$UP"
python3 -B -m unittest discover -s tests \
  -p 'test_review_agent_orchestration_upstreams_20261021.py' -v
```

The audit prints JSON to stdout, does not run external code, and exits nonzero
if expected local files or upstream pins are absent. No claimed runtime
performance, ROI, security audit or deployment follows from a green result.

## Implemented integration (production commit 4908cb56b)

This evaluation now includes real, narrowly scoped changes to EmpireOS's
**existing** Executive/completion-board dispatchers, without changing its
shared department worker implementation.
It does not introduce a new business, agent, queue, timer, DB, UI or service.

**Orcha-informed no-progress circuit breaker.** Shared
`empire_os/department_adapter_registry.py` is consumed by both EXISTING dispatchers; it inspects the CURRENT
`department_worker.py` as inert source data and never edits or executes it. When a previously blocked item
has `specialist_adapter_required`, it may reopen only if the current worker
supports the exact target (and an existing safe script actually exists).
For additional directly handled targets introduced by parallel owners, the
guard uses Python AST parsing to detect only explicit literal target branches
inside the worker's current handler and the worker's literal `SAFE_COMMANDS`
manifest, without importing or executing the module; symlink escapes are rejected.
Unknown targets stay blocked. The worker still independently enforces
authorization; a target matching the registry is not a permission grant.
Queue identity and existing blocker semantics remain unchanged.

A **read-only** snapshot of the production queue found 334
`specialist_adapter_required` blocks, of which **329** target components
with no existing worker adapter and **5** were already supported. Under the
new policy the 329 stay blocked rather than being repeatedly reopened by
dispatch loops. This is a prospective classification, not measured runtime
savings. Additional block reasons remain untouched.

**Paperclip-informed goal alignment.** The current
`astra_department_dispatch.py` now reads goal priorities already authored
by `astra_executive.py` and maps validated ACTIVE integer goal priorities
to bounded queue priority **80..87**. This is deliberately below the
completion-board's minimum class priority **88**; founder-gated or externally
authorized tasks remain ineligible. Missing/duplicate/malformed goal metadata
falls back to original priority 80. No AI-generated impact, delegability,
confidence, DICE score or outcome claims are inferred. Existing queued work
keeps its previous priority (no forced reprioritisation). Dispatch snapshot
reports effective priority, newly goal-prioritised count, and specialist
retry holds without reading tenant source bodies.

These are deliberate adaptations of documented upstream **ideas**, not
copies of upstream implementation code. Neither vendor application was
installed into the EmpireOS runtime. Nora and Red Hat template-agent require
a separate justified runtime/identity/telemetry scope; head-of-ai-template's
DICE ranking requires independently verified input factors and is not
automatically adopted.

**Tests / scope:** bounded synthetic regression testing covers absent and
present adapters, legitimate evidence holds, queue deduplication, ten
repeated no-progress dispatches, parallel-owner adapter detection,
source-path symlink isolation, direct-target registry synchronisation,
active/malformed/duplicate goal handling, priority ordering, exclusion of
founder-gated steps, and unchanged priorities for previously queued work.

**Production receipt:** Selectively committed seven integration files as `4908cb56b` on the existing EmpireOS production branch, without touching the pre-existing modified shared worker. The production checkout passed 59 scoped regression tests and seven static audit tests. The existing department heartbeat completed with exit status 0 and subsequently wrote a dispatch snapshot at 2026-10-21T22:49:03Z containing both new counters (0 holds and 0 newly prioritised for that particular current plan). That is evidence of runtime loading, not measured throughput or revenue improvement. The existing ops-control timer already owns `ops_sentinel` observation; no second sentinel runtime was added. Rollback requires a reviewed revert of commit `4908cb56b` that preserves concurrent production edits.
