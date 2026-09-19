from pathlib import Path

import pytest

from empire_os.coder.ast_patch import AstPatchEngine, find_python_symbol
from empire_os.coder.dependencies import DependencyIndex
from empire_os.coder.patch import PatchEngine, PatchError
from empire_os.coder.repo import RepoIntelligence
from empire_os.coder.roles import ROLES


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    pkg = tmp_path / "empire_os"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text(
        "def value():\n    return 1\n\nclass Engine:\n    pass\n"
    )
    (pkg / "service.py").write_text(
        "from empire_os.core import value\n\ndef use():\n    return value()\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("from empire_os.core import value\n")
    (tests / "test_service.py").write_text("from empire_os.service import use\n")
    return tmp_path


def test_symbol_range_and_symbol_patch(tmp_path):
    root = make_repo(tmp_path)
    source = (root / "empire_os/core.py").read_text()
    symbol = find_python_symbol(source, "value")
    assert symbol.start_line == 1
    engine = AstPatchEngine(PatchEngine(root, runtime_root=root / "runtime"))
    result = engine.replace_python_symbol(
        "task_ast",
        "empire_os/core.py",
        "value",
        "def value():\n    return 2",
    )
    assert result["before_sha256"] != result["after_sha256"]
    assert "return 2" in (root / "empire_os/core.py").read_text()


def test_symbol_patch_requires_unique_symbol():
    with pytest.raises(PatchError, match="exactly one"):
        find_python_symbol("def x(): pass\ndef x(): pass\n", "x")


def test_dependency_index_selects_impacted_tests(tmp_path):
    root = make_repo(tmp_path)
    repo = RepoIntelligence(root)
    index = DependencyIndex(repo).build()
    assert "empire_os/service.py" in index.dependents("empire_os/core.py")
    tests = index.impacted_tests(["empire_os/core.py"])
    assert "tests/test_core.py" in tests
    assert "tests/test_service.py" in tests


def test_specialist_roles_separate_patch_and_review_authority():
    assert ROLES["backend"].can_patch is True
    assert ROLES["backend"].can_verify is False
    assert ROLES["security"].can_patch is False
    assert ROLES["security"].can_verify is True
    assert ROLES["reviewer"].can_patch is False
    assert ROLES["architect"].can_patch is False


def test_symbol_patch_preserves_class_method_indentation(tmp_path):
    root = make_repo(tmp_path)
    target = root / "empire_os/methods.py"
    target.write_text(
        "class Engine:\n"
        "    def value(self):\n"
        "        return 1\n",
        encoding="utf-8",
    )
    engine = AstPatchEngine(
        PatchEngine(root, runtime_root=root / "runtime")
    )
    engine.replace_python_symbol(
        "task_method",
        "empire_os/methods.py",
        "value",
        "def value(self):\n    return 2",
    )
    updated = target.read_text(encoding="utf-8")
    assert "    def value(self):" in updated
    assert "        return 2" in updated

    import ast
    tree = ast.parse(updated)
    class_node = tree.body[0]
    assert isinstance(class_node, ast.ClassDef)
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.name == "value"
        for node in class_node.body
    )
