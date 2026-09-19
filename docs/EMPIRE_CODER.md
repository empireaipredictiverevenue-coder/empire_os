# Empire Coder

Status: foundation implementation, OBSERVE-first, production activation gated.

Empire Coder is the internal developer-intelligence layer for EmpireOS. It builds, debugs, tests, improves and maintains EmpireOS through a governed engineering pipeline rather than unrestricted autonomous shell access.

## Engineering Loop

TASK -> UNDERSTAND -> SEARCH REPO -> PLAN -> CANDIDATE A/B -> COMPARE -> SYNTHESIZE -> PATCH -> RUN -> TEST -> DIAGNOSE -> REPAIR -> VERIFY -> DIFF -> APPROVAL

The first model response is never actionable. Empire Coder generates at least two independent candidates, performs a comparative critique, synthesizes a new final candidate, and only then allows the result to enter patch/verification flow. Independent verification still happens after synthesis.

## Safety Kernel

Empire Coder defaults to OBSERVE.

The default developer profile may read/search the assigned Git worktree, build bounded context packs, create targeted patches, run allowlisted tests/lint/type/build checks, inspect Git status/diff/log, use local model inference, and generate verification/candidate reports.

Commit, push, merge, deploy, production migrations, service control, production credentials, outbound actions and funds remain human-gated or denied.

Protected paths include recovery, toop, tools and .git. Repository retrieval also refuses .env files, private-key formats and credential/secret files.

## Repository Intelligence

RepoIntelligence provides bounded tree mapping, text search, Python symbol search, import discovery, test discovery, line-window excerpts and Blueprint retrieval.

Context packs use evidence windows around relevant matches instead of dumping whole repositories. Blueprint v6 remains the default architectural reference.

## Durable Task State

Local state lives under runtime/coder with restrictive permissions and atomic writes.

Recovery preserves objective, status, phase, plan, completed work, unresolved issues, discovered files, decisions, required tests, verification state, approvals, best-of-N proposals and refined next-command proposals.

Every significant orchestration event refreshes a versioned compact recovery snapshot. Every model call refreshes and consumes that latest durable snapshot instead of relying on raw chat/session history.

The staged canonical Supabase migration adds coder_tasks, coder_steps, coder_tool_runs, coder_findings, coder_patches, coder_proposals, coder_command_proposals, coder_context_snapshots, coder_knowledge_sources and coder_verifications.

The dedicated empire_coder_state role has no commercial or payment authority. The login remains passwordless until explicitly provisioned.

## Mandatory Best-of-N Output Refinement

Model output follows CANDIDATE A/B -> COMPARATIVE CRITIQUE -> SYNTHESIZED FINAL.

A proposal cannot be actionable unless at least two independent candidates exist, a comparative critique exists, at least one revision occurred, and the synthesized result is non-empty and not identical to candidate one.

Next-command selection follows the same rule. Two command candidates are generated, compared, synthesized into strict argv JSON, and then passed through command policy. A raw model command is never executed directly.

These invariants exist in runtime code and the staged database schema, so draft number one cannot silently become an action.

## Knowledge Garden

Empire Coder does not treat all repository knowledge as equally trustworthy.

The knowledge garden classifies engineering guidance as ACTIVE, REVIEW or QUARANTINED using provenance, canonical-source precedence, exact-duplicate detection and stale-architecture flags.

Default ACTIVE knowledge is intentionally narrow:
- docs/BLUEPRINT_V6.md (highest roadmap/status authority);
- AGENTS.md;
- docs/EMPIRE_CODER.md;
- curated MCP/tooling guidance;
- curated webapp-testing guidance.

The large legacy prompt corpus is REVIEW-only by default. Blueprint v5 and the stale prompt index are explicitly quarantined. Original source files are not deleted; the garden writes an active manifest under runtime/coder/knowledge and retrieval admits guarded knowledge only when ACTIVE.

This prevents stale paths, obsolete payment architecture, duplicate prompts and low-value prompt noise from poisoning local-model context.

## Symbol-Aware Engineering

Empire Coder now has Python AST-aware symbol replacement, dependency/reverse-dependency indexing, and impacted-test selection.

Specialist roles are defined for Architect, Backend, Frontend, QA, Security and Reviewer. Writer and verifier authority are separated; defining a role does not grant production authority.

## Structured Patch Proposals

Empire Coder can now convert model output into a machine-checkable patch proposal rather than treating free-form prose as executable engineering intent.

Supported bounded operations:
- exact single-match replacement;
- Python symbol replacement using AST symbol boundaries;
- creation of a new file with an allowlisted source/document suffix.

Structured patches follow the same best-of-N rule: two independent JSON candidates, comparative critique, new synthesized JSON proposal, then live repository validation.

Validation checks target path/workspace boundaries, protected paths, live symbol existence, exact-match counts, Python syntax, requested symbol identity, security patterns and expected-test paths.

A structured proposal is validated when created and **validated again immediately before local patch application**. If the repository changed between proposal and application, Empire Coder rejects the stale proposal instead of applying it approximately.

Expected tests from an accepted structured proposal are carried into durable task state. HTTP still exposes no patch/apply endpoint.

## Task-Scoped Knowledge Promotion

The Knowledge Garden remains globally strict, but a task can explicitly promote a REVIEW source for that task only.

Promotion requires:
- explicit approval;
- a recorded reason;
- source status REVIEW;
- a hash pin of the exact reviewed content.

ACTIVE sources need no promotion. QUARANTINED knowledge can never be promoted.

If a promoted source changes after approval, its hash no longer matches and it automatically drops out of that task's retrieval context until re-reviewed. Promotion manifests are private runtime state and do not change the global knowledge manifest.

## Distinct Writer and Verifier Models

Model routing is role-aware.

The auto-detected local qwen3-coder:30b profile is writer-only. A model-based verifier must use a different configured provider/model identity; Empire Coder excludes the writer identity when selecting the verifier route.

If no distinct verifier model is configured, model review is reported as unavailable rather than letting the writer review itself. Deterministic security, syntax, tests and diff verification remain authoritative in all cases. Model review is advisory only and cannot turn a deterministic FAIL into a PASS.

## Local Models

Ollama is installed user-local and bound to 127.0.0.1:11434.

Primary local model: qwen3-coder:30b.

Measured on this host at 16K context:
- about 18 GB on disk
- about 20 GB runtime memory
- about 15 prompt tokens/sec
- about 4.65 generated tokens/sec
- about 35 GiB RAM still available during the benchmark

CPU is the bottleneck, so Empire Coder uses targeted context windows and capped outputs. Proposal-worker PLAN jobs cap repository evidence at 6,000 characters and each best-of-N candidate/synthesis output at 1,200 characters. Local Ollama requests explicitly set `think=false`; deliberate comparison still comes from the mandatory two-candidate + critique + synthesis pipeline, avoiding a second hidden reasoning pass on every CPU-local 30B request.

The model router remains provider-agnostic. Local Ollama is preferred when healthy and installed; hosted providers can later be added as escalation/fallback routes.

## Tool and Patch Controls

The command runner never uses shell=True, filters its environment, forces OBSERVE, enforces timeouts, applies allow/approval/deny command policy and scrubs secret-like stdout/stderr before returning or storing it.

The patch engine enforces read-before-write, exact replacements, atomic writes, rollback checkpoints and workspace boundaries.

## Independent Verifier

The verifier is separate from drafting/refinement. It checks security patterns, protected paths, Git state, git diff --check, selected validation commands and self-build scope.

Verdicts are PASS, FAIL or PASS_WITH_WARNINGS.

A successful verification moves a task to AWAITING_APPROVAL. It does not commit, merge or deploy.

## Controlled Self-Build

Empire Coder can improve itself only through the same governed pipeline. Default self-build scope is empire_os/coder, tests/coder, docs/EMPIRE_CODER, scripts/empire_coder and config/empire_coder.

Self-build cannot silently widen its own authority.

## Internal API and Resumable Worker

Empire Coder exposes a deliberately narrow internal control plane under `/v1/coder`.

Public-safe:
- `GET /v1/coder/health` — reports OBSERVE mode, whether the internal API is enabled, and confirms there is no production authority.

Internal-token gated and disabled by default:
- create/read task state;
- read compact task memory;
- enqueue a PLAN job;
- enqueue a NEXT_COMMAND proposal job;
- read job status;
- read knowledge-garden health.

The API has no run, execute, patch, commit, merge, deploy, migration or service-control endpoint.

Activation requires both:
- `EMPIRE_CODER_API_ENABLED=1`
- a non-empty `EMPIRE_CODER_API_INTERNAL_TOKEN`

Authentication uses constant-time token comparison. Without both configuration values, control endpoints fail closed.

Long model work is placed in `runtime/coder/jobs` rather than executed inside the HTTP request.

`LocalJobQueue` supports atomic claim, completion/failure state and stale-running-job recovery. `CoderTaskWorker` currently processes only:
- PLAN — best-of-N implementation planning, proposal only;
- NEXT_COMMAND — best-of-N command synthesis and policy classification, never execution.

`empire-coder-worker.service` and `empire-coder-worker.timer` are installed on the EmpireOS host. The timer is enabled and invokes one bounded worker pass per minute. The worker remains filesystem-restricted and network-restricted to localhost so it can reach local Ollama without receiving general outbound network access. Its oneshot start timeout is explicitly 30 minutes so bounded CPU-local 30B planning jobs are not killed by the shorter systemd default timeout.

## Runtime Packaging

`empire-ollama.service` is installed and enabled for reboot persistence. The installer deliberately leaves an already-healthy localhost Ollama process undisturbed; after reboot the systemd unit owns startup. It binds Ollama to localhost, loads one model at a time, allows one parallel generation and runs as ubuntu with restrictive systemd protections.

`scripts/install_empire_coder_services.sh` is the explicit root activation helper. `--check` performs non-mutating unit validation. Root installation verifies all units again, installs them under `/etc/systemd/system`, enables Ollama for reboot persistence, enables/starts the Coder worker timer, preserves an already-healthy localhost Ollama process, and refuses to launch a duplicate worker. It does not enable the internal Coder API or provision production credentials.

## Next Slices

1. Canonical PostgreSQL state transport after migration and credential approval.
2. Structured model-to-patch schema with AST validation before patch application.
3. Separate writer and verifier model routes so verification can use a different model/provider.
4. Task-specific knowledge promotion so REVIEW sources can be temporarily activated with provenance.
5. Disposable sandbox/container for higher-risk development commands.
6. Multi-agent execution scheduler using specialist roles and file-ownership DAG.
7. Repeatable local/hosted coding benchmark suite for model-routing decisions.
8. Controlled end-to-end self-build benchmark that creates a patch, tests it, verifies it and stops at approval.
9. Internal API authorization integration with the broader EmpireOS identity layer once that canonical layer is selected.
10. Production activation only after API auth, state transport, worker runtime and rollback controls have been reviewed together.
