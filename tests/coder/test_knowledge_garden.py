from pathlib import Path

from empire_os.coder.context import ContextBuilder
from empire_os.coder.knowledge_garden import (
    KnowledgeGarden,
    KnowledgeStatus,
)
from empire_os.coder.models import CoderTask
from empire_os.coder.repo import RepoIntelligence


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint v6\nCanonical USDT on BSC architecture.\n"
    )
    (tmp_path / "AGENTS.md").write_text(
        "Inspect before modifying. Keep OBSERVE mode.\n"
    )

    skills = tmp_path / "empire_os/skills_library/skills/mcp-builder"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "# Coding\nUse targeted patches and verify every change. " * 5
    )

    prompts = tmp_path / "empire_os/data/prompts"
    prompts.mkdir(parents=True)
    (prompts / "stale.txt").write_text(
        "Use /root/empire_os/ and USDC on Solana. " * 8
    )
    (prompts / "review.txt").write_text(
        "Generic coding helper guidance without canonical authority. " * 8
    )
    duplicate = "duplicate legacy prompt content " * 8
    (prompts / "dup1.txt").write_text(duplicate)
    (prompts / "dup2.txt").write_text(duplicate)
    return tmp_path


def test_garden_quarantines_stale_and_duplicates(tmp_path):
    root = make_repo(tmp_path)
    report = KnowledgeGarden(root).scan()
    by_path = {row.path: row for row in report.records}

    assert by_path["docs/BLUEPRINT_V6.md"].status is KnowledgeStatus.ACTIVE
    assert (
        by_path["docs/BLUEPRINT_V6.md"].authority
        > by_path["AGENTS.md"].authority
    )
    assert (
        by_path["empire_os/skills_library/skills/mcp-builder/SKILL.md"].status
        is KnowledgeStatus.ACTIVE
    )
    assert (
        by_path["empire_os/data/prompts/stale.txt"].status
        is KnowledgeStatus.QUARANTINED
    )
    assert "obsolete_payment_rail" in by_path[
        "empire_os/data/prompts/stale.txt"
    ].flags
    assert (
        by_path["empire_os/data/prompts/review.txt"].status
        is KnowledgeStatus.REVIEW
    )
    assert (
        by_path["empire_os/data/prompts/dup2.txt"].status
        is KnowledgeStatus.QUARANTINED
    )


def test_manifest_sync_contains_active_only_in_active_lane(tmp_path):
    root = make_repo(tmp_path)
    garden = KnowledgeGarden(root)
    payload = garden.sync_manifest()
    active = {row["path"] for row in payload["active"]}
    review = {row["path"] for row in payload["review"]}
    quarantined = {row["path"] for row in payload["quarantined"]}

    assert "docs/BLUEPRINT_V6.md" in active
    assert "empire_os/skills_library/skills/mcp-builder/SKILL.md" in active
    assert "empire_os/data/prompts/review.txt" in review
    assert "empire_os/data/prompts/stale.txt" in quarantined
    assert (
        root / "runtime/coder/knowledge/active.json"
    ).is_file()


def test_context_builder_filters_guarded_knowledge(tmp_path):
    root = make_repo(tmp_path)
    repo = RepoIntelligence(root)
    garden = KnowledgeGarden(root)
    report = garden.scan()
    builder = ContextBuilder(
        repo,
        active_knowledge_paths=set(garden.active_paths(report)),
    )
    task = CoderTask(
        id="coder_test",
        objective="Review coding guidance",
        workspace=str(root),
        blueprint_path="docs/BLUEPRINT_V6.md",
    )

    pack = builder.build(
        task,
        terms=["coding", "USDC", "targeted patches"],
    )
    paths = {doc.path for doc in pack.documents}

    assert "docs/BLUEPRINT_V6.md" in paths
    assert "empire_os/skills_library/skills/mcp-builder/SKILL.md" in paths
    assert "empire_os/data/prompts/stale.txt" not in paths
    assert "empire_os/data/prompts/review.txt" not in paths
