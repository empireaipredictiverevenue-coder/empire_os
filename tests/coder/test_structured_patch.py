import json

import pytest

from empire_os.coder.context import ContextPack
from empire_os.coder.models import ModelRoute
from empire_os.coder.patch import PatchEngine
from empire_os.coder.provider import ModelResponse
from empire_os.coder.structured_patch import (
    PatchOperation,
    StructuredPatchError,
    StructuredPatchProposal,
    StructuredPatchRefiner,
    StructuredPatchValidator,
)


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    pkg = tmp_path / "empire_os"
    pkg.mkdir()
    (pkg / "core.py").write_text(
        "def value():\n    return 1\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        "from empire_os.core import value\n",
        encoding="utf-8",
    )
    return tmp_path


def route():
    return ModelRoute("fake", "fake-model", "test")


def context():
    return ContextPack("goal", {}, (), (), 4000)


def test_python_symbol_proposal_validates_live_symbol(tmp_path):
    root = make_repo(tmp_path)
    validator = StructuredPatchValidator(root)
    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_PYTHON_SYMBOL,
        target_path="empire_os/core.py",
        symbol="value",
        new_text="def value():\n    return 2\n",
        rationale="return updated value",
        expected_tests=("tests/test_core.py",),
    )
    result = validator.validate(proposal)
    assert result.valid is True
    assert result.reasons == ()


def test_python_symbol_proposal_rejects_wrong_symbol_shape(tmp_path):
    root = make_repo(tmp_path)
    validator = StructuredPatchValidator(root)
    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_PYTHON_SYMBOL,
        target_path="empire_os/core.py",
        symbol="value",
        new_text="def other():\n    return 2\n",
        rationale="wrong symbol",
    )
    result = validator.validate(proposal)
    assert result.valid is False
    assert "python_replacement_must_define_requested_symbol" in result.reasons


def test_replace_exact_python_validates_resulting_syntax(tmp_path):
    root = make_repo(tmp_path)
    validator = StructuredPatchValidator(root)
    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_EXACT,
        target_path="empire_os/core.py",
        old_text="return 1",
        new_text="return (",
        rationale="bad syntax",
    )
    result = validator.validate(proposal)
    assert result.valid is False
    assert "python_syntax_invalid" in result.reasons


def test_protected_path_proposal_is_rejected(tmp_path):
    root = make_repo(tmp_path)
    protected = root / "recovery"
    protected.mkdir()
    (protected / "old.py").write_text("x = 1\n")
    validator = StructuredPatchValidator(root)
    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_EXACT,
        target_path="recovery/old.py",
        old_text="1",
        new_text="2",
        rationale="should fail",
    )
    result = validator.validate(proposal)
    assert result.valid is False
    assert any("path_validation_failed" in reason for reason in result.reasons)


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, request):
        self.calls.append(request.instruction)
        return ModelResponse(
            "fake",
            "fake-model",
            self.responses[len(self.calls) - 1],
        )


def test_best_of_n_structured_patch_is_parsed_and_validated(tmp_path):
    root = make_repo(tmp_path)
    payload = {
        "operation": "replace_python_symbol",
        "target_path": "empire_os/core.py",
        "symbol": "value",
        "old_text": None,
        "new_text": "def value():\n    return 2\n",
        "rationale": "bounded symbol replacement",
        "expected_tests": ["tests/test_core.py"],
    }
    provider = FakeProvider([
        json.dumps({**payload, "rationale": "candidate one"}),
        json.dumps({**payload, "rationale": "candidate two"}),
        "candidate two is more bounded",
        json.dumps(payload),
    ])
    candidate = StructuredPatchRefiner(
        provider,
        StructuredPatchValidator(root),
    ).propose(
        task_id="coder_test",
        objective="update value",
        context=context(),
        route=route(),
    )
    assert candidate.eligible is True
    assert len(candidate.candidate_texts) == 2
    assert candidate.proposal.symbol == "value"
    assert candidate.validation.valid is True


def test_non_json_synthesis_is_rejected(tmp_path):
    root = make_repo(tmp_path)
    provider = FakeProvider([
        "{}",
        "{}",
        "critique",
        "not-json",
    ])
    with pytest.raises(StructuredPatchError, match="strict JSON"):
        StructuredPatchRefiner(
            provider,
            StructuredPatchValidator(root),
        ).propose(
            task_id="coder_test",
            objective="update value",
            context=context(),
            route=route(),
        )


def test_orchestrator_applies_validated_structured_symbol_patch(tmp_path):
    from empire_os.coder.orchestrator import EmpireCoder
    from empire_os.coder.structured_patch import (
        PatchValidation,
        StructuredPatchCandidate,
    )

    root = make_repo(tmp_path)
    (root / "docs").mkdir()
    (root / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nGoverned coding.\n",
        encoding="utf-8",
    )
    coder = EmpireCoder(root)
    task = coder.create_task("Update value safely")

    proposal = StructuredPatchProposal(
        operation=PatchOperation.REPLACE_PYTHON_SYMBOL,
        target_path="empire_os/core.py",
        symbol="value",
        new_text="def value():\n    return 2\n",
        rationale="bounded symbol update",
        expected_tests=("tests/test_core.py",),
    )
    validation = coder.structured_patch_validator.validate(proposal)
    assert validation.valid is True

    candidate = StructuredPatchCandidate(
        candidate_texts=("candidate a", "candidate b"),
        critique="candidate b is more bounded",
        synthesized_text=json.dumps(proposal.as_dict()),
        proposal=proposal,
        validation=validation,
    )
    result = coder.apply_structured_patch(task.id, candidate)

    assert result["path"] == "empire_os/core.py"
    assert "return 2" in (
        root / "empire_os/core.py"
    ).read_text(encoding="utf-8")
    restored = coder.load_task(task.id)
    assert "tests/test_core.py" in restored.tests_required
