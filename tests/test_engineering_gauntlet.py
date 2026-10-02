import pytest
from empire_os.engineering_gauntlet import (
    GauntletCandidate,
    evaluate_gauntlet,
)

def candidate(**overrides):
    row=dict(
        action_key="a1",
        component="qualification_worker_v2",
        authority="internal_write",
        evidence_refs=("architecture:1",),
        architecture_contract=True,
        fresh_context_critic_passed=True,
        tests_policy_passed=True,
        independent_verify_ready=True,
        diff_clean=True,
        reversible=True,
        consequential=False,
    )
    row.update(overrides)
    return GauntletCandidate(**row)

def test_internal_reversible_action_can_pass():
    d=evaluate_gauntlet(candidate())
    assert d.decision=="READY_FOR_INTERNAL_EXECUTION"
    assert d.execution_authority=="internal_write"

def test_missing_stage_blocks():
    d=evaluate_gauntlet(candidate(tests_policy_passed=False))
    assert d.decision=="BLOCKED"
    assert "tests_security_policy" in d.blockers

def test_consequential_action_requires_founder_gate():
    d=evaluate_gauntlet(candidate(
        authority="founder_gate",
        consequential=True,
        reversible=False,
    ))
    assert d.decision=="READY_FOR_APPROVAL"
    assert d.execution_authority=="none"
    assert d.founder_gate_required is True

def test_internal_authority_cannot_be_consequential():
    with pytest.raises(ValueError):
        evaluate_gauntlet(candidate(consequential=True))
