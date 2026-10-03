"""Deterministic fast-path for repeatable Empire Coder advisory PLAN jobs.

The fast-path is intentionally narrow. It may only emit non-actionable plans
for known high-volume planning families whose required workflow is already
encoded by EmpireOS doctrine. It performs no repository mutation, deployment,
network action, outbound communication, payment, or authority expansion.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .jobs import CoderJob, JobKind, JobStatus, LocalJobQueue
from .orchestrator import EmpireCoder


PROVIDER = "empire_deterministic_plan"
MODEL = "empire_contract_v1"


@dataclass(frozen=True)
class FastPlan:
    family: str
    text: str
    rationale: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def classify_fast_plan(
    objective: str,
    payload: Mapping[str, Any] | None = None,
) -> str | None:
    normalized = re.sub(r"\s+", " ", _text(objective)).lower()
    terms = {
        _text(value).lower()
        for value in ((payload or {}).get("terms") or ())
        if _text(value)
    }

    if (
        normalized.startswith(
            "plan only: integrate this founder directive"
        )
        and "directive:" in normalized
    ):
        return "founder_directive"

    if (
        normalized.startswith(
            "plan only: advance this existing predictive cloud opportunity"
        )
        and "canonical opportunity factory" in normalized
    ):
        return "predictive_cloud_opportunity"

    if (
        "completion_review_then_implement_or_verify" in terms
        and "completion owner for" in normalized
        and "evidence-backed plan only" in normalized
    ):
        return "completion_owner"

    if (
        "completion_review_then_implement_or_verify" in terms
        and "canonical completion board item:" in normalized
        and "revenue-first programme" in normalized
    ):
        return "completion_review"

    if (
        normalized.startswith("completion owner for ")
        and "produce an evidence-backed plan only for remaining items"
        in normalized
    ):
        return "completion_owner"

    if (
        "prepare_to_gate_and_verify_prerequisites" in normalized
        or "prepare_to_gate_and_verify_prerequisites" in terms
    ):
        return "gate_prerequisites"

    return None


def _completion_item(objective: str) -> str:
    match = re.search(
        r"Canonical completion board item:\s*(.+?)\.\s*Revenue-first programme",
        objective,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return "the referenced canonical completion-board item"


_DIRECTIVE_STOPWORDS = {
    "about", "after", "again", "against", "architecture", "authority",
    "build", "business", "covering", "create", "data", "directive",
    "empire", "empireos", "existing", "first", "founder", "from",
    "integrate", "internal", "into", "must", "only", "plan", "produce",
    "rather", "refined", "relevant", "runtime", "search", "should",
    "system", "than", "that", "their", "then", "this", "through",
    "unknown", "with", "without",
}


def _directive_text(objective: str) -> str:
    marker = "Directive:"
    if marker not in objective:
        return objective.strip()
    return objective.split(marker, 1)[1].strip()


def _directive_terms(text: str) -> list[str]:
    terms = []
    for raw in re.findall(r"[a-zA-Z0-9_\-]{4,}", text.lower()):
        clean = raw.strip("-_")
        if (
            len(clean) >= 4
            and clean not in _DIRECTIVE_STOPWORDS
            and clean not in terms
        ):
            terms.append(clean)
    return terms[:24]


def _repo_contract_matches(
    workspace: Any,
    directive: str,
    *,
    limit: int = 16,
) -> list[str]:
    root = workspace if hasattr(workspace, "resolve") else None
    if root is None:
        return []
    root = root.resolve()
    terms = _directive_terms(directive)
    if not terms:
        return []

    suffixes = {
        ".py", ".md", ".sh", ".service", ".timer",
        ".toml", ".yaml", ".yml",
    }
    scored: list[tuple[int, str]] = []
    for base_name in ("empire_os", "docs", "scripts", "deploy"):
        base = root / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            try:
                if path.stat().st_size > 750_000:
                    continue
            except OSError:
                continue
            rel = str(path.relative_to(root))
            rel_low = rel.lower()
            path_hits = sum(term in rel_low for term in terms)
            if path_hits == 0:
                try:
                    content = path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    ).lower()
                except OSError:
                    continue
                content_hits = sum(term in content for term in terms)
            else:
                # Path identity is much stronger than a generic content mention.
                content_hits = 0
            score = path_hits * 10 + content_hits
            if score > 0:
                scored.append((score, rel))
    return [
        rel
        for _, rel in sorted(
            scored,
            key=lambda row: (-row[0], row[1]),
        )[:max(1, limit)]
    ]


def _founder_directive_plan(
    objective: str,
    workspace: Any,
) -> FastPlan:
    directive = _directive_text(objective)
    matches = _repo_contract_matches(workspace, directive)
    observed = (
        "\n".join(f"- {path}" for path in matches)
        if matches
        else "- No deterministic path match; preserve UNKNOWN and require targeted repo review."
    )
    plan = f"""Empire deterministic Founder Directive integration plan

Directive
- {directive}

Existing Empire candidates observed by deterministic repo scan
{observed}

Reuse-first architecture
1. Inspect the observed candidates and their direct imports/contracts before proposing any new module.
2. Select one canonical owner for each required capability; reject parallel subsystems.
3. Preserve canonical EmpireDB, Evidence Fabric, execution-plane and Founder-surface ownership where applicable.

Data and automation
4. Define only the smallest missing contract: inputs, provenance, freshness, outputs, idempotency and failure semantics.
5. Wire event/timer automation through existing Empire queues/services rather than chat-driven operation.
6. Keep UNKNOWN as UNKNOWN; do not fabricate economics, demand, buyer intent, outcomes or approvals.

Acceptance and observability
7. Add focused contract tests plus relevant regressions and git diff --check.
8. Add read-only operational evidence/Daily Results fields for freshness, blockers, retries and next-safe-action.
9. Require live runtime evidence before marking the directive complete.

Deployment and rollback
10. Keep the delta reversible and isolated; use the governed execution plane for any code mutation.
11. Define service/config rollback before promotion.

Commercial and authority gates
12. State the commercial effect only when supported by evidence.
13. No live outbound, binding terms, funds/mainnet, destructive infrastructure, revenue recognition or authority expansion without the existing Founder gate.

Output
- Produce the bounded architecture delta, exact owned files/tests, automation wiring and gate packet. No production action is performed by this PLAN."""
    return FastPlan(
        family="founder_directive",
        text=plan,
        rationale="Founder Directive planning can reuse deterministic repo ownership discovery",
    )


def build_fast_plan(
    objective: str,
    payload: Mapping[str, Any] | None = None,
    *,
    workspace: Any = None,
) -> FastPlan | None:
    family = classify_fast_plan(objective, payload)
    if family is None:
        return None

    if family == "founder_directive":
        return _founder_directive_plan(objective, workspace)

    if family == "completion_owner":
        match = re.search(
            r"Completion owner for\s+(.+?)\.\s+Produce an evidence-backed "
            r"PLAN ONLY for remaining items\.\s+Classify each\s+(.+?)\.\s+"
            r"No deploy/send/payment/DB mutation steps",
            objective,
            flags=re.IGNORECASE | re.DOTALL,
        )
        owner = (
            re.sub(r"\s+", " ", match.group(1)).strip()
            if match else "the referenced completion domain"
        )
        pending = (
            re.sub(r"\s+", " ", match.group(2)).strip()
            if match else "the remaining canonical items"
        )
        plan = f"""Empire deterministic completion-owner plan

Owner domain
- {owner}

Pending scope
- {pending}

Classification pass
1. Evaluate each pending item independently as VERIFIED_DONE, NEEDS_WIRING, NEEDS_LIVE_PROOF, FOUNDER_GATE, REAL_WORLD_EVIDENCE_REQUIRED or LEGACY_RETIRED.
2. Reuse canonical modules and current runtime evidence; do not count code existence alone as completion.
3. Keep unknown facts UNKNOWN and preserve provenance for every completion claim.

Convergence
4. For VERIFIED_DONE items, assemble exact code, focused-test, live-runtime and canonical-data evidence.
5. For NEEDS_WIRING items, identify the smallest bounded integration delta and existing owner module.
6. For NEEDS_LIVE_PROOF items, specify the read-only live verification required.
7. For FOUNDER_GATE or REAL_WORLD_EVIDENCE_REQUIRED items, prepare prerequisites only and stop at the gate.
8. Mark legacy work retired only when a canonical replacement and migration evidence exist.

Verification
9. Require focused tests, relevant regressions, git diff --check and runtime evidence before closure.
10. Surface blockers and next-safe-action to the existing Founder/operations status path where applicable.

Authority
- No deployment, external send, binding terms, DB activation, funds, payment mutation, revenue recognition, destructive infrastructure or authority expansion.
- Any code mutation must go through the governed builder pipeline.

Output
- Produce one evidence-backed closure/gap packet for the owner domain. No production action is performed by this PLAN."""
        return FastPlan(
            family=family,
            text=plan,
            rationale="completion-owner classification workflow is deterministic",
        )

    if family == "gate_prerequisites":
        item = _completion_item(objective)
        plan = f"""Empire deterministic gate-prerequisite plan

Scope
- Gated item: {item}

Prerequisite verification
1. Identify the exact external/founder gate and the canonical module that would act only after approval.
2. Verify every safe internal prerequisite: identity, evidence freshness, product/version binding, pricing/terms evidence, capacity, destination, fulfilment readiness, suppression/compliance, payment rail or other domain-specific preconditions.
3. Assemble exact evidence references and current blockers. Missing facts remain UNKNOWN.
4. If any prerequisite is incomplete, route only the smallest reversible internal remediation through the governed builder/execution plane.
5. Re-run focused tests and read-only live verification after internal remediation.

Gate packet
6. Produce a concise operator packet containing the proposed action, evidence, expected effect, unresolved risk, rollback/abort condition and exact approval still required.
7. Stop before the gated action.

Authority
- Do not send externally, accept binding terms, move funds, mutate payment state, recognize revenue, deploy destructively or claim the gated event occurred.
- No gate may be inferred from historical context.

Output
- VERIFIED_PREREQUISITES or BLOCKED_PREREQUISITES plus the exact remaining approval/evidence requirement. No production action is performed by this PLAN."""
        return FastPlan(
            family=family,
            text=plan,
            rationale="founder/real-world gate preparation follows a fixed safe contract",
        )

    if family == "completion_review":
        item = _completion_item(objective)
        plan = f"""Empire deterministic completion-review plan

Scope
- Canonical item: {item}
- Treat code existence as insufficient proof of completion.
- Reuse existing production modules; do not create a duplicate subsystem.

Evidence pass
1. Locate the canonical implementation, architecture contract, tests, runtime unit/timer, canonical data path and Founder surface where applicable.
2. Classify the item as VERIFIED_DONE, NEEDS_WIRING, NEEDS_LIVE_PROOF, FOUNDER_GATE, REAL_WORLD_EVIDENCE_REQUIRED or LEGACY_RETIRED.
3. Keep missing facts UNKNOWN. Do not infer approvals, buyer intent, economics, revenue or external outcomes.

Smallest next delta
4. If VERIFIED_DONE, assemble exact code/test/live/data evidence for checklist closure.
5. If incomplete, identify only the smallest production delta, exact owned files, focused tests, required runtime verification and rollback boundary.
6. Any implementation must go through the governed builder/execution plane with allowed paths and mutation leases.

Verification
7. Run focused tests, relevant regressions, git diff --check and read-only live verification.
8. Require canonical data/runtime evidence before DONE.

Authority gates
- No live outbound, binding terms, funds, payment-state mutation, revenue recognition, destructive infrastructure or authority expansion.
- Preserve existing founder gates.

Output
- Produce a bounded gate packet or independently evidenced closure packet. No production action is performed by this PLAN."""
        return FastPlan(
            family=family,
            text=plan,
            rationale="canonical completion workflow is already deterministic",
        )

    plan = """Empire deterministic Predictive Cloud opportunity plan

Architecture
- Reuse the canonical Signal/Search/Market evidence fabrics, Opportunity Radar, Opportunity Factory, Predictive Revenue/Quant, Astra, product/catalog, fulfilment and Founder surfaces.
- Do not create a parallel opportunity subsystem.

Evidence completion
1. Read the opportunity evidence already named by the task and identify missing fields required by the canonical Opportunity Factory contract.
2. Map each missing field to an existing Empire evidence producer where one exists; otherwise mark the field UNKNOWN and propose one bounded adapter only if necessary.
3. Preserve provenance, observed_at/freshness, confidence and evidence references on every promoted fact.

Canonical promotion
4. Normalize only evidence-backed fields into the existing Opportunity Factory schema.
5. Keep buyer intent, demand, economics, market share and revenue UNKNOWN unless independently observed.
6. Deduplicate against existing opportunity identity before any canonical write proposal.

Economics and product path
7. Use Predictive Revenue/Quant only when explicit revenue, cost and timing inputs exist.
8. Map the opportunity to an existing product/offer and fulfilment contract where evidence supports it; otherwise record the exact readiness blocker.

Automation
9. Wire evidence refresh -> Opportunity Radar -> Opportunity Factory -> Astra safe internal work using existing queues and idempotency keys.
10. Add observability for source freshness, promotion decisions, blockers, retries and next-safe-action.

Verification
11. Add focused contract tests, dedupe/idempotency tests, UNKNOWN-not-zero tests and relevant regression coverage.
12. Verify live runtime read-only and confirm canonical data before claiming completion.

Authority gates
- No outreach, terms acceptance, payment/funds action, revenue recognition, fabricated evidence or authority expansion.
- Any mutable code work proceeds only through the governed builder pipeline.

Output
- Produce an evidence-completion packet identifying reusable modules, exact missing evidence, proposed bounded delta, focused tests, automation wiring and Founder-surface evidence. No production action is performed by this PLAN."""
    return FastPlan(
        family=family,
        text=plan,
        rationale="canonical opportunity-completion workflow is already deterministic",
    )


def persist_fast_plan(
    coder: EmpireCoder,
    job: CoderJob,
    plan: FastPlan,
) -> dict[str, Any]:
    coder.store.save_proposal(
        job.task_id,
        {
            "task_id": job.task_id,
            "provider": PROVIDER,
            "model": MODEL,
            "stage": "REFINED",
            "draft": plan.text,
            "candidate_drafts": [plan.text],
            "critique": (
                "Deterministic contract fast-path; no model critique required."
            ),
            "refined": plan.text,
            "revision_count": 1,
            "actionable": False,
            "fastpath_family": plan.family,
            "fastpath_rationale": plan.rationale,
        },
    )
    return {
        "kind": JobKind.PLAN.value,
        "stage": "REFINED",
        "candidate_count": 1,
        "revision_count": 1,
        "drafted": True,
        "refined": True,
        "actionable_patch": False,
        "proposal_persisted": True,
        "model_inference": False,
        "deterministic_fastpath": True,
        "fastpath_family": plan.family,
        "provider": PROVIDER,
        "production_mutation": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }


def drain_fast_plans(
    coder: EmpireCoder,
    queue: LocalJobQueue,
    *,
    max_jobs: int = 80,
    worker_id: str = "coder-fastpath",
) -> dict[str, Any]:
    """Drain only recognized fast-path PLAN jobs from the pending queue."""
    bounded = max(1, min(int(max_jobs), 200))
    completed: list[dict[str, Any]] = []
    skipped_unrecognized = 0
    candidates = queue.list_pending(kind=JobKind.PLAN)

    for candidate in candidates:
        if len(completed) >= bounded:
            break
        try:
            task = coder.store.load(candidate.task_id)
        except Exception:
            continue
        plan = build_fast_plan(
            task.objective,
            candidate.payload,
            workspace=coder.workspace,
        )
        if plan is None:
            skipped_unrecognized += 1
            continue

        claimed = queue.claim_specific(
            candidate.id,
            worker_id=worker_id,
            lease_seconds=120,
        )
        if claimed is None:
            continue
        try:
            result = persist_fast_plan(coder, claimed, plan)
            terminal = queue.complete(claimed, result)
            memory = getattr(coder, "memory", None)
            if memory is not None:
                memory.retire(
                    claimed.task_id,
                    terminal_state=terminal.status.value,
                    job_id=terminal.id,
                )
            completed.append({
                "job_id": terminal.id,
                "task_id": terminal.task_id,
                "family": plan.family,
                "priority": terminal.priority,
                "status": terminal.status.value,
            })
        except Exception as exc:
            queue.fail(
                claimed,
                f"deterministic_fastpath_failed:{type(exc).__name__}:{exc}",
            )

    return {
        "schema_version": "empire.coder.plan-fastpath-drain.v1",
        "status": "AVAILABLE",
        "max_jobs": bounded,
        "completed_count": len(completed),
        "skipped_unrecognized_count": skipped_unrecognized,
        "completed": completed,
        "model_inference": False,
        "production_mutation": False,
        "external_execution_performed": False,
        "execution_authority": "none",
    }
