"""Cross-agent board is evidence-only and blocks unsafe direct promotion."""
from pathlib import Path

import pytest

from scripts import review_empire_cross_agent_release_board_20261020 as board


def test_owner_inventory_does_not_claim_release_authority(monkeypatch,tmp_path):
    production=tmp_path/"production";production.mkdir()
    dirs={path for _,path in board.OWNER_WORKTREES}
    orig=Path.is_dir
    monkeypatch.setattr(Path,"is_dir",lambda p: True if str(p) in dirs else orig(p))
    calls=[]
    def fake_git(root,*args,cap=1_000_000):
        calls.append(args)
        match=args[0]
        if match=="rev-parse":
            return "a"*40 if str(root)==str(production) else "b"*40
        if match=="branch":return "feature/owner"
        if match=="status":return " M empire_os/shared.py" if str(root)==str(production) else ""
        if match=="merge-base":return "c"*40
        if match=="diff":return "empire_os/shared.py\nempire_os/new.py"
        raise AssertionError(args)
    monkeypatch.setattr(board,"_git",fake_git)
    out=board.review_board(str(production))
    assert out["priority_owner_count"]==len(board.OWNER_WORKTREES)
    assert out["production_dirty_change_rows"]==1
    for item in out["owner_reviews"]:
        assert item["state"]=="PRODUCTION_PATH_COLLISIONS_REQUIRE_REVIEW"
        assert item["production_uncommitted_file_path_collision_count"]==1
        assert item["direct_merge_authorized"] is False
    assert out["merges_executed"] is False
    assert out["deployments_performed"] is False
    assert out["database_writes"] is False
    assert all(x[0] in ("rev-parse","branch","merge-base","diff","status")
               for x in calls)


def test_missing_owner_worktree_explicit_hold(monkeypatch,tmp_path):
    prod=tmp_path/"prod";prod.mkdir()
    monkeypatch.setattr(Path,"is_dir",lambda p: False)
    def git(root,*args,cap=1_000_000):
        return "a"*40 if args[0]=="rev-parse" else "main" if args[0]=="branch" else ""
    monkeypatch.setattr(board,"_git",git)
    out=board.review_board(str(prod))
    assert all(x["state"]=="OWNER_WORKTREE_MISSING" for x in out["owner_reviews"])
    assert out["owner_dependencies_independently_satisfied"] is False
    assert out["all_agent_work_automatically_promoted"] is False


def test_git_errors_do_not_turn_into_a_clean_merge(monkeypatch,tmp_path):
    prod=tmp_path/"prod";prod.mkdir()
    monkeypatch.setattr(Path,"is_dir",lambda p:True)
    def git(root,*args,cap=1_000_000):
        if args[0] in ("rev-parse","branch","status"):return "a"*40 if args[0]=="rev-parse" else ""
        raise ValueError("inaccessible owner")
    monkeypatch.setattr(board,"_git",git)
    out=board.review_board(str(prod))
    assert all(x["state"]=="GIT_EVIDENCE_UNAVAILABLE_HOLD" for x in out["owner_reviews"])
    assert not out["merges_executed"]
