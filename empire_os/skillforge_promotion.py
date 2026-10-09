"""Fail-closed skill promotion review plans. No trust-registry write path.

Human/Founder sign-off, legal and security reviews, and a verified evaluation
must occur separately before an explicit approval is recorded in source control.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from typing import Any

from empire_os.skill_exchange import SKILLS_ROOT
from empire_os.skillforge_benchmark import score_holdout
from empire_os.skillforge_evaluation import evaluate_skill
from empire_os.skill_trust import SkillTrustError, read_trust_registry, load_pinned_skill


REQUIRED_REVIEWS = (
    'verify_independent_holdout_labels_and_source_evidence',
    'confirm_baseline_candidate_run_reproducibility',
    'test_with_real_authorized_agent_in_isolated_environment',
    'complete_tenant_privacy_and_prompt_injection_review',
    'clear_licence_intellectual_property_and_ownership',
    'obtain_explicit_founder_approval_for_exact_skill_digest',
    'record_scoped_review_evidence_and_approval_as_reviewed_code_change',
)


def promotion_preflight(name: str, *, root: Path = SKILLS_ROOT,
                        suite: dict[str, Any] | None = None,
                        trust_registry: Path | None = None) -> dict[str, Any]:
    """Render a safe promotion request; never conclude production quality."""
    static = evaluate_skill(name, root=root)
    digest = static.get('sha256')
    blocks = []
    if not static.get('passed'):
        blocks.append('static_skill_contract_incomplete')
    benchmark = None
    if suite is None:
        blocks.append('independently_labelled_holdout_not_supplied')
    else:
        benchmark = score_holdout(suite)
        if benchmark['skill_name'] != name or digest is None or benchmark['skill_sha256'] != digest:
            blocks.append('benchmark_skill_identity_or_digest_mismatch')
        if not benchmark['numeric_gate_pass']:
            blocks.append('holdout_numeric_safety_or_quality_gate_failed')
    already_approved = False
    if trust_registry is not None:
        try:
            registry = read_trust_registry(trust_registry)
            load_pinned_skill(name, root=root, registry=registry)
            already_approved = True
        except (SkillTrustError, OSError, ValueError):
            pass
    review_ready = not blocks
    return {
        'schema_version': 'empire.skillforge.promotion_preflight.v1',
        'name': name,
        'skill_sha256': digest,
        'status': 'READY_FOR_INDEPENDENT_REVIEW' if review_ready else 'BLOCKED',
        'evaluation_kind': 'offline_submitted_outputs_not_agent_execution',
        'benchmark': benchmark,
        'static_checks_passed': bool(static.get('passed')),
        'numeric_review_ready': review_ready,
        'blocks': blocks,
        'required_reviews': list(REQUIRED_REVIEWS),
        'founder_approval_recorded': False,
        'independent_performance_verified': False,
        'already_approved_in_registry': already_approved,
        'promoted': False,
        'trust_registry_changed': False,
        'agent_execution_performed': False,
        'execution_authority': 'none',
    }
