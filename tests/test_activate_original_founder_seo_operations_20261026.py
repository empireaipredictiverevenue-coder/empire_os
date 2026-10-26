"""Scoped Founder SEO release: original owner hashes, idempotent preflight, rollback."""
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import activate_original_founder_seo_operations_20261026 as release


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256(data).hexdigest()


def setup_release(tmp_path, monkeypatch):
    stage = tmp_path / "existing_founder"
    candidate = tmp_path / "seo_candidate" / "web"
    stage.mkdir(mode=0o700)
    candidate.mkdir(parents=True)
    (stage / ".next").mkdir()
    (candidate / ".next").mkdir()
    (stage / ".next/BUILD_ID").write_text("ORIGINAL")
    (candidate / ".next/BUILD_ID").write_text("CANDIDATE")
    old_results = b"Original results no SEO link"
    new_results = b"Original results plus new SEO link"
    sha_old=_write(stage/release.RESULTS_PAGE,old_results)
    sha_new=_write(candidate/release.RESULTS_PAGE,new_results)
    sha_route=_write(candidate/release.SEO_PAGE,b"Private SEO Operations route")
    a=_write(stage/release.OWNER_PAGES[0],b"Founder source")
    b=_write(stage/release.OWNER_PAGES[1],b"Founder API source")
    _write(candidate/release.OWNER_PAGES[0],b"Founder source")
    _write(candidate/release.OWNER_PAGES[1],b"Founder API source")
    monkeypatch.setattr(release,"STAGE",stage)
    monkeypatch.setattr(release,"CANDIDATE",candidate)
    monkeypatch.setattr(release,"RELEASE",candidate.parent)
    monkeypatch.setattr(release,"BACKUP",candidate.parent/"activation_backups")
    monkeypatch.setattr(release,"ORIGINAL_BUILD","ORIGINAL")
    monkeypatch.setattr(release,"NEW_BUILD","CANDIDATE")
    monkeypatch.setattr(release,"ORIGINAL_RESULTS_SHA",sha_old)
    monkeypatch.setattr(release,"CANDIDATE_RESULTS_SHA",sha_new)
    monkeypatch.setattr(release,"CANDIDATE_SEO_SHA",sha_route)
    monkeypatch.setattr(release,"ORIGINAL_FOUNDER_SHA",a)
    monkeypatch.setattr(release,"ORIGINAL_FOUNDER_API_SHA",b)
    monkeypatch.setattr(release.os,"geteuid",lambda:0)
    commands=[]
    def command(*args):
        commands.append(args)
        if args[:3]==("systemctl","show","empire-founder-console.service"):
            return str(stage)
        if args[:3]==("systemctl","is-active","empire-founder-console.service"):
            return "active"
        if args[:3]==("systemctl","restart","empire-founder-console.service"):
            return ""
        raise AssertionError(args)
    monkeypatch.setattr(release,"call",command)
    monkeypatch.setattr(release,"status",lambda url: (200,b"safe"))
    monkeypatch.setattr(release,"verify_live",lambda:{
        "/founder":200,"/founder/results":200,"/founder/seo-operations":200,
        "/founder/agency":200,
    })
    return stage,candidate,commands,command


def test_guarded_original_release_exact_two_sources_and_preserves_rollback(tmp_path,monkeypatch):
    stage,candidate,cmd,_=setup_release(tmp_path,monkeypatch)
    assert release.preflight()["writes"] is False
    output=release.activate()
    assert output["status"]=="ORIGINAL_FOUNDER_SEO_OPERATIONS_LIVE_VERIFIED"
    assert output["source_files_changed"]==2
    assert (stage/".next/BUILD_ID").read_text()=="CANDIDATE"
    assert (candidate.parent/"activation_backups/.next.original/BUILD_ID").read_text()=="ORIGINAL"
    assert (candidate.parent/"activation_backups/results.page.original.tsx").read_bytes()==b"Original results no SEO link"
    assert (stage/release.SEO_PAGE).read_bytes()==b"Private SEO Operations route"
    assert any(x[:2]==("systemctl","restart") for x in cmd)
    assert (candidate.parent/"activation_result.json").is_file()


def test_unexpected_owner_change_fails_before_any_live_mutation(tmp_path,monkeypatch):
    stage,candidate,_,_=setup_release(tmp_path,monkeypatch)
    (stage/release.OWNER_PAGES[1]).write_text("Other owner changed API source")
    with pytest.raises(release.ReleaseHeld,match="UNRELATED_FOUNDER_OWNER_CHANGED"):
        release.activate()
    assert not (stage/release.SEO_PAGE).exists()
    assert (stage/".next/BUILD_ID").read_text()=="ORIGINAL"
    assert not (candidate.parent/"activation_backups").exists()


def test_failed_restart_rolls_back_old_build_and_navigation(tmp_path,monkeypatch):
    stage,candidate,commands,success=setup_release(tmp_path,monkeypatch)
    restarts=[]
    def fail_once(*args):
        if args[:2]==("systemctl","restart"):
            restarts.append(args)
            if len(restarts)==1:
                raise RuntimeError("simulated_restart_failure")
            return ""
        return success(*args)
    monkeypatch.setattr(release,"call",fail_once)
    with pytest.raises(RuntimeError,match="simulated_restart_failure"):
        release.activate()
    assert (stage/".next/BUILD_ID").read_text()=="ORIGINAL"
    assert (stage/release.RESULTS_PAGE).read_bytes()==b"Original results no SEO link"
    assert not (stage/release.SEO_PAGE).exists()
    assert len(restarts)==2
    assert not (candidate.parent/"activation_result.json").exists()
