from empire_os.coder.orchestrator import EmpireCoder


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text("# Blueprint\n")
    pkg = tmp_path / "empire_os"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("def value():\n    return 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("from empire_os.core import value\n")
    return tmp_path


def test_orchestrator_symbol_patch_and_test_selection(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    task = coder.create_task("Change value safely")
    coder.patch_python_symbol(
        task.id,
        "empire_os/core.py",
        "value",
        "def value():\n    return 2",
    )
    assert "return 2" in (root / "empire_os/core.py").read_text()
    assert coder.impacted_tests(["empire_os/core.py"]) == (
        "tests/test_core.py",
    )


def test_specialist_roles_keep_writer_and_verifier_separate(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    roles = coder.specialist_roles()
    assert roles["backend"]["can_patch"] is True
    assert roles["backend"]["can_verify"] is False
    assert roles["reviewer"]["can_patch"] is False
    assert roles["reviewer"]["can_verify"] is True

from empire_os.coder.models import ModelRoute
from empire_os.coder.provider import ModelResponse
from empire_os.coder.router import ModelProfile


class FakeCommandProvider:
    name = "fake-command"

    def __init__(self):
        self.responses = [
            "git status --short",
            "git diff --check",
            "The diff check directly verifies candidate patch integrity.",
            '{"argv":["git","diff","--check"]}',
        ]
        self.calls = []

    def complete(self, request):
        self.calls.append(request.instruction)
        return ModelResponse(
            self.name,
            "fake-command-model",
            self.responses[len(self.calls) - 1],
        )


def test_orchestrator_persists_refined_next_command_in_memory(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(
        root,
        model_profiles=(
            ModelProfile(
                "fake-command",
                "fake-command-model",
                capability=3,
                cost_tier=0,
                local=True,
            ),
        ),
    )
    provider = FakeCommandProvider()
    coder.providers.register(provider)
    task = coder.create_task("Verify the current patch")
    context = coder.build_context(task.id, terms=["Blueprint"])

    proposal = coder.propose_next_command(
        task.id,
        "Choose the safest verification command",
        context,
    )

    assert proposal.eligible is True
    assert proposal.argv == ("git", "diff", "--check")
    assert len(proposal.candidate_texts) == 2

    saved = coder.store.latest_command_proposal(task.id)
    assert saved["candidate_texts"] == [
        "git status --short",
        "git diff --check",
    ]
    assert saved["decision"] == "allow"

    memory = coder.memory.load(task.id)
    assert memory["latest_command_proposal"]["candidate_count"] == 2
    assert memory["latest_command_proposal"]["argv"] == [
        "git",
        "diff",
        "--check",
    ]
    assert memory["latest_command_proposal"]["eligible"] is True
