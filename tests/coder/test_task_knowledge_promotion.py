import os

import pytest

from empire_os.coder.knowledge_garden import KnowledgeGarden


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nCanonical EmpireOS architecture.\n"
    )

    core = tmp_path / "empire_os/skills_library/skills/mcp-builder"
    core.mkdir(parents=True)
    (core / "SKILL.md").write_text(
        "# MCP Builder\nUse governed tooling and targeted verification. " * 6
    )

    review = tmp_path / "empire_os/skills_library/skills/frontend-design"
    review.mkdir(parents=True)
    (review / "SKILL.md").write_text(
        "# Frontend Design\nTask-specific frontend guidance. " * 8
    )

    prompts = tmp_path / "empire_os/data/prompts"
    prompts.mkdir(parents=True)
    (prompts / "stale.txt").write_text(
        "Legacy path /root/empire_os/ should be used. " * 8
    )
    return tmp_path


def test_review_source_requires_explicit_task_approval(tmp_path):
    root = make_repo(tmp_path)
    garden = KnowledgeGarden(root)
    review_path = "empire_os/skills_library/skills/frontend-design/SKILL.md"

    with pytest.raises(PermissionError, match="explicit approval"):
        garden.promote_for_task(
            "coder_task_1",
            [review_path],
            reason="needed for UI task",
            approved=False,
        )

    payload = garden.promote_for_task(
        "coder_task_1",
        [review_path],
        reason="needed for UI task",
        approved=True,
    )
    assert payload["entries"][0]["path"] == review_path

    global_active = set(garden.active_paths())
    task_active = set(garden.active_paths_for_task("coder_task_1"))
    assert review_path not in global_active
    assert review_path in task_active

    manifest = (
        root
        / "runtime/coder/knowledge/task_promotions/coder_task_1.json"
    )
    assert os.stat(manifest).st_mode & 0o777 == 0o600


def test_promoted_source_drops_out_after_content_changes(tmp_path):
    root = make_repo(tmp_path)
    garden = KnowledgeGarden(root)
    review_path = "empire_os/skills_library/skills/frontend-design/SKILL.md"
    garden.promote_for_task(
        "coder_task_2",
        [review_path],
        reason="UI task",
        approved=True,
    )
    assert review_path in garden.active_paths_for_task("coder_task_2")

    (root / review_path).write_text(
        "# Frontend Design\nChanged content requires re-review. " * 8
    )
    assert review_path not in garden.active_paths_for_task("coder_task_2")


def test_quarantined_source_can_never_be_promoted(tmp_path):
    root = make_repo(tmp_path)
    garden = KnowledgeGarden(root)
    with pytest.raises(PermissionError, match="quarantined"):
        garden.promote_for_task(
            "coder_task_3",
            ["empire_os/data/prompts/stale.txt"],
            reason="try stale guidance",
            approved=True,
        )
