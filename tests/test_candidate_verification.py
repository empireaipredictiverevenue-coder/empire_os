from pathlib import Path

import pytest

from empire_os.candidate_verification import (
    CandidateVerificationError,
    _path_allowed,
)


def test_candidate_verifier_path_policy_is_prefix_bounded():
    assert _path_allowed(
        "empire_os/search_intelligence/scoring.py",
        ("empire_os/search_intelligence/",),
    )
    assert not _path_allowed(
        "empire_os/revenue_pulse.py",
        ("empire_os/search_intelligence/",),
    )


def test_candidate_verifier_requires_branch_and_paths(tmp_path):
    from empire_os.candidate_verification import verify_candidate_branch

    with pytest.raises(CandidateVerificationError):
        verify_candidate_branch(
            tmp_path,
            proposal_branch="",
            allowed_paths=("empire_os/",),
            pytest_targets=(),
        )
    with pytest.raises(CandidateVerificationError):
        verify_candidate_branch(
            tmp_path,
            proposal_branch="pi/job-x",
            allowed_paths=(),
            pytest_targets=(),
        )


def test_candidate_verifier_declares_no_merge_or_deploy_authority():
    import empire_os.candidate_verification as module
    text = Path(module.__file__).read_text(encoding="utf-8")
    assert '"production_merge": False' in text
    assert '"production_deploy": False' in text
    assert '"execution_authority": "none"' in text
