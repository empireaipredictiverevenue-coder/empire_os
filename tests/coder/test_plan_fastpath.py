import subprocess

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, JobStatus, LocalJobQueue
from empire_os.coder.plan_fastpath import (
    build_fast_plan,
    classify_fast_plan,
    drain_fast_plans,
)


def workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def test_classifies_only_known_high_volume_plan_families():
    opportunity = (
        "PLAN ONLY: advance this existing Predictive Cloud opportunity toward "
        "the canonical Opportunity Factory without inventing evidence."
    )
    completion = (
        "Department work delegated by Astra Executive. "
        "Canonical completion board item: Test item. Revenue-first programme."
    )
    assert classify_fast_plan(opportunity, {}) == "predictive_cloud_opportunity"
    assert classify_fast_plan(
        completion,
        {"terms": ["completion_review_then_implement_or_verify"]},
    ) == "completion_review"
    assert classify_fast_plan("Design a novel architecture", {}) is None


def test_fast_plans_are_non_actionable_and_preserve_gates():
    plan = build_fast_plan(
        (
            "Department work delegated by Astra Executive. "
            "Canonical completion board item: Buyer settlement. "
            "Revenue-first programme."
        ),
        {"terms": ["completion_review_then_implement_or_verify"]},
    )
    assert plan is not None
    assert "Buyer settlement" in plan.text
    assert "No live outbound" in plan.text
    assert "revenue recognition" in plan.text
    assert "governed builder" in plan.text


def test_claim_specific_claims_only_requested_job(tmp_path):
    root = workspace(tmp_path)
    queue = LocalJobQueue(root)
    first = queue.enqueue(task_id="task-a", kind=JobKind.PLAN, priority=10)
    second = queue.enqueue(task_id="task-b", kind=JobKind.PLAN, priority=99)

    claimed = queue.claim_specific(first.id, worker_id="fast")

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status is JobStatus.RUNNING
    assert queue.get(second.id).status is JobStatus.PENDING


def test_drain_fast_plans_skips_novel_and_uses_zero_model_inference(tmp_path):
    root = workspace(tmp_path)
    runtime = root / "runtime/coder"
    coder = EmpireCoder(root, runtime_root=runtime)
    queue = LocalJobQueue(root, runtime_root=runtime)

    fast_task = coder.create_task(
        "PLAN ONLY: advance this existing Predictive Cloud opportunity toward "
        "the canonical Opportunity Factory without inventing evidence or "
        "creating a duplicate subsystem."
    )
    novel_task = coder.create_task("Design a novel scheduler architecture.")
    fast_job = queue.enqueue(
        task_id=fast_task.id,
        kind=JobKind.PLAN,
        priority=50,
    )
    novel_job = queue.enqueue(
        task_id=novel_task.id,
        kind=JobKind.PLAN,
        priority=100,
    )

    result = drain_fast_plans(coder, queue, max_jobs=10)

    assert result["completed_count"] == 1
    assert result["model_inference"] is False
    assert queue.get(fast_job.id).status is JobStatus.COMPLETED
    assert queue.get(novel_job.id).status is JobStatus.PENDING
    proposal = coder.store.latest_proposal(fast_task.id)
    assert proposal["provider"] == "empire_deterministic_plan"
    assert proposal["actionable"] is False

def test_completion_owner_and_gate_prerequisite_are_fastpath_safe():
    owner = (
        "Completion owner for Predictive Cloud / Quant. Produce an "
        "evidence-backed PLAN ONLY for remaining items. Classify each "
        "Item A | Item B. No deploy/send/payment/DB mutation steps and "
        "do not infer founder approval."
    )
    gate = (
        "Department work delegated by Astra Executive. "
        "action=prepare_to_gate_and_verify_prerequisites; "
        "Canonical completion board item: Continue real outbound. "
        "Revenue-first programme."
    )

    assert classify_fast_plan(owner, {}) == "completion_owner"
    assert classify_fast_plan(gate, {}) == "gate_prerequisites"

    owner_plan = build_fast_plan(owner, {})
    gate_plan = build_fast_plan(gate, {})
    assert owner_plan is not None
    assert "NEEDS_LIVE_PROOF" in owner_plan.text
    assert "No deployment" in owner_plan.text
    assert gate_plan is not None
    assert "Stop before the gated action" in gate_plan.text
    assert "Do not send externally" in gate_plan.text



def test_founder_directive_fastpath_is_repo_aware(tmp_path):
    root = workspace(tmp_path)
    (root / "empire_os").mkdir()
    (root / "empire_os/tam_market_intelligence.py").write_text(
        "def build_tam(): pass\n",
        encoding="utf-8",
    )
    objective = (
        "PLAN ONLY: integrate this Founder Directive into the existing EmpireOS "
        "business rather than creating a disconnected duplicate. Directive: "
        "Build native TAM market intelligence and segmentation."
    )

    plan = build_fast_plan(objective, {}, workspace=root)

    assert plan is not None
    assert plan.family == "founder_directive"
    assert "tam_market_intelligence.py" in plan.text
    assert "No live outbound" in plan.text
    assert "No production action is performed" in plan.text
