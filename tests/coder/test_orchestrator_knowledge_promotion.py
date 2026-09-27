import pytest

from empire_os.coder.orchestrator import EmpireCoder


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nCanonical architecture.\n"
    )
    review = (
        tmp_path
        / "empire_os/skills_library/skills/frontend-design"
    )
    review.mkdir(parents=True)
    (review / "SKILL.md").write_text(
        "# Frontend Design\nUNIQUE_TASK_FRONTEND_GUIDANCE " * 8
    )
    return tmp_path


def test_task_promotion_changes_only_that_tasks_context(tmp_path):
    root = make_repo(tmp_path)
    coder = EmpireCoder(root)
    path = (
        "empire_os/skills_library/skills/"
        "frontend-design/SKILL.md"
    )
    first = coder.create_task("Frontend task")
    second = coder.create_task("Other task")

    before = coder.build_context(
        first.id,
        terms=["UNIQUE_TASK_FRONTEND_GUIDANCE"],
    )
    assert path not in {
        doc.path for doc in before.documents
    }

    with pytest.raises(PermissionError):
        coder.promote_task_knowledge(
            first.id,
            [path],
            reason="needed for this task",
            approved=False,
        )

    status = coder.promote_task_knowledge(
        first.id,
        [path],
        reason="needed for this task",
        approved=True,
    )
    assert status["promoted"] == 1

    promoted = coder.build_context(
        first.id,
        terms=["UNIQUE_TASK_FRONTEND_GUIDANCE"],
    )
    assert path in {
        doc.path for doc in promoted.documents
    }

    other = coder.build_context(
        second.id,
        terms=["UNIQUE_TASK_FRONTEND_GUIDANCE"],
    )
    assert path not in {
        doc.path for doc in other.documents
    }
