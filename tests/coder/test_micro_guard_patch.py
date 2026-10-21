"""Real source-style tests of the model-backed, bounded guard pilot."""
import json
import subprocess

import pytest

from empire_os.coder.micro_guard_patch import (
    _safe_guard, _source_guard_location, propose_micro_guard,
)
from empire_os.coder.models import ModelRoute
from empire_os.coder.provider import ModelResponse
from empire_os.coder.structured_patch import StructuredPatchError


class FakeLocalModel:
    def __init__(self, *conditions):
        self.conditions = list(conditions)
        self.calls = []

    def complete(self, req):
        self.calls.append(req)
        next_output = self.conditions.pop(0)
        return ModelResponse(
            provider="llama_cpp",
            model="qwen2.5-coder:1.5b",
            text=json.dumps({"condition": next_output}),
        )


@pytest.fixture
def code_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    code = tmp_path / "empire_os/coder/ollama_provider.py"
    code.parent.mkdir(parents=True)
    code.write_text(
        'class OllamaProvider:\n'
        '    def models(self, body):\n'
        '        names = []\n'
        '        for row in body.get("models") or []:\n'
        '            name = str(row.get("name") or "").strip()\n'
        '            if name:\n'
        '                names.append(name)\n'
        '        return tuple(names)\n',
        encoding="utf-8",
    )
    return tmp_path, code


def make_candidate(root, responses):
    return propose_micro_guard(
        workspace=root, provider=FakeLocalModel(*responses),
        route=ModelRoute("llama_cpp", "qwen2.5-coder:1.5b", "local", True, 0),
        task_id="real_source_scoped_pilot_test",
        objective="OllamaProvider.models skips null rows in model catalog.",
        source_path="empire_os/coder/ollama_provider.py",
        required_tests=("tests/coder/test_ollama_provider.py",),
    )


def test_two_independent_guard_proposals_yield_eligible_exact_source_patch(code_repo):
    root, source_file = code_repo
    original = source_file.read_text()
    condition = "not isinstance(row, dict)"
    candidate = make_candidate(root, (condition, condition))
    assert candidate.eligible
    assert len(candidate.candidate_texts) == 2
    assert "DETERMINISTIC_AST_REVIEW" in candidate.critique
    assert candidate.proposal.operation.value == "replace_exact"
    assert candidate.proposal.target_path == "empire_os/coder/ollama_provider.py"
    assert candidate.proposal.expected_tests == ("tests/coder/test_ollama_provider.py",)
    assert source_file.read_text() == original  # proposal only; no live patch
    patched = original.replace(
        candidate.proposal.old_text, candidate.proposal.new_text, 1
    )
    compile(patched, str(source_file), "exec")
    namespace = {}
    exec(compile(patched, str(source_file), "exec"), namespace)
    assert namespace["OllamaProvider"]().models({"models": [None, {"name": "ok"}]}) == ("ok",)


@pytest.mark.parametrize("condition", [
    "__import__('os').system('whoami')",
    "True",
    "row is None",
    "not isinstance(row, dict) or True",
    "not isinstance(other, dict)",
])
def test_model_outputs_outside_pure_mapping_guard_denied(code_repo, condition):
    root, source = code_repo
    before = source.read_bytes()
    with pytest.raises(StructuredPatchError, match="unsafe_or_incorrect"):
        make_candidate(root, (condition, condition))
    assert source.read_bytes() == before


def test_independent_disagreement_fails_closed(code_repo):
    root, _ = code_repo
    # Each is syntactically valid but a textual disagreement is rejected.
    with pytest.raises(StructuredPatchError, match="independent_outputs_disagree"):
        make_candidate(
            root,
            ("not isinstance(row, dict)", "not isinstance( row, dict )"),
        )


def test_no_unguarded_unique_source_prevents_model_inference(code_repo):
    root, path = code_repo
    path.write_text("def unrelated():\n    return 1\n")
    model = FakeLocalModel("not isinstance(row, dict)")
    with pytest.raises(StructuredPatchError, match="one_unique"):
        propose_micro_guard(
            workspace=root, provider=model,
            route=ModelRoute("llama_cpp", "qwen2.5-coder:1.5b", "local", True, 0),
            task_id="guard_test",
            objective="OllamaProvider.models skips null rows in model catalog.",
            source_path="empire_os/coder/ollama_provider.py",
            required_tests=("tests/coder/test_ollama_provider.py",),
        )
    assert not model.calls
