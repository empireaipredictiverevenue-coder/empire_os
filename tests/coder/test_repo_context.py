from empire_os.coder.context import ContextBuilder
from empire_os.coder.models import CoderTask
from empire_os.coder.repo import RepoIntelligence


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "BLUEPRINT_V6.md").write_text("# Blueprint\nEmpire Coder must remain OBSERVE.\n")
    pkg = tmp_path / "empire_os"
    pkg.mkdir()
    (pkg / "sample.py").write_text("import json\n\nclass RevenueEngine:\n    pass\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_sample.py").write_text("def test_sample(): pass\n")
    protected = tmp_path / "recovery"
    protected.mkdir()
    (protected / "secret.py").write_text("RevenueEngine = 'old'\n")
    return tmp_path


def test_repo_intelligence_is_targeted_and_skips_protected(tmp_path):
    root = make_repo(tmp_path)
    repo = RepoIntelligence(root)
    tree = repo.tree(max_depth=4)
    assert "empire_os/sample.py" in tree
    assert not any(path.startswith("recovery/") for path in tree)
    hits = repo.search("RevenueEngine")
    assert len(hits) == 1
    assert hits[0].path == "empire_os/sample.py"
    symbols = repo.symbols("Revenue")
    assert symbols[0].text == "RevenueEngine"
    assert repo.python_imports("empire_os/sample.py") == ["json"]
    assert repo.test_candidates("empire_os/sample.py") == ["tests/test_sample.py"]


def test_context_pack_includes_blueprint_and_relevant_file(tmp_path):
    root = make_repo(tmp_path)
    repo = RepoIntelligence(root)
    builder = ContextBuilder(repo)
    task = CoderTask(
        id="coder_test",
        objective="Improve RevenueEngine safely",
        workspace=str(root),
        blueprint_path="docs/BLUEPRINT_V6.md",
    )
    pack = builder.build(task, terms=["RevenueEngine"], symbol_terms=["RevenueEngine"], budget_chars=20_000)
    paths = [doc.path for doc in pack.documents]
    assert paths[0] == "docs/BLUEPRINT_V6.md"
    assert "empire_os/sample.py" in paths
    assert pack.symbols[0]["symbol"] == "RevenueEngine"

def test_symbol_definition_precedes_generic_import_hits(tmp_path):
    root = make_repo(tmp_path)
    # Re-export the symbol so generic text search sees an import-style hit too.
    (root / "empire_os/__init__.py").write_text(
        "from empire_os.sample import RevenueEngine\n"
    )
    repo = RepoIntelligence(root)
    builder = ContextBuilder(repo)
    task = CoderTask(
        id="coder_symbol_priority",
        objective="Inspect RevenueEngine",
        workspace=str(root),
        blueprint_path="docs/BLUEPRINT_V6.md",
    )
    pack = builder.build(
        task,
        terms=["RevenueEngine"],
        symbol_terms=["RevenueEngine"],
        budget_chars=6000,
    )
    paths = [doc.path for doc in pack.documents]
    assert "empire_os/sample.py" in paths
    assert paths.index("empire_os/sample.py") < (
        paths.index("empire_os/__init__.py")
        if "empire_os/__init__.py" in paths
        else 999
    )
    assert len(paths) == len(set(paths))
