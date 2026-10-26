"""Guarded existing Founder SEO V2 publisher: exact source, backup, rollback."""
from hashlib import sha256
from pathlib import Path
import pytest

from scripts import activate_founder_seo_tool_suite_v2_20261026 as owner


def put(path:Path,value:str)->str:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value)
    return sha256(value.encode()).hexdigest()


def configured(tmp_path,monkeypatch):
    live=tmp_path/"live"
    proposal=tmp_path/"candidate"/"web"
    live.mkdir(mode=0o700)
    proposal.mkdir(parents=True)
    (live/".next").mkdir()
    (proposal/".next").mkdir()
    (live/".next/BUILD_ID").write_text("OLD")
    (proposal/".next/BUILD_ID").write_text("NEW")
    old_page=put(live/owner.SEO,"SEO original")
    new_page=put(proposal/owner.SEO,"SEO unified command centre")
    new_workbench=put(proposal/owner.WORKBENCH,"interactive tool suite")
    unchanged={}
    for name in owner.OWNER_HASHES:
        unchanged[name]=put(live/name,name+" original")
        put(proposal/name,name+" original")
    for key,value in {
        "LIVE":live,"PROPOSAL":proposal,"OWNER":proposal.parent,
        "BACKUP":proposal.parent/"activation_backups",
        "OLD_BUILD":"OLD","NEW_BUILD":"NEW",
        "OLD_SEO_SHA":old_page,"NEW_SEO_SHA":new_page,
        "NEW_WORKBENCH_SHA":new_workbench,"OWNER_HASHES":unchanged,
    }.items():
        monkeypatch.setattr(owner,key,value)
    monkeypatch.setattr(owner.os,"geteuid",lambda:0)
    commands=[]
    def command(*args):
        commands.append(args)
        if args[:3]==("systemctl","show","empire-founder-console.service"):
            return str(live)
        if args[:3]==("systemctl","is-active","empire-founder-console.service"):
            return "active"
        if args[:3]==("systemctl","restart","empire-founder-console.service"):
            return ""
        raise AssertionError(args)
    monkeypatch.setattr(owner,"cmd",command)
    monkeypatch.setattr(owner,"http",lambda url:(200,b"healthy"))
    monkeypatch.setattr(owner,"verify",lambda:dict.fromkeys(owner.ROUTES,200))
    return live,proposal,commands,command


def test_exact_source_changes_and_backup(tmp_path,monkeypatch):
    live,proposal,commands,_=configured(tmp_path,monkeypatch)
    assert owner.check()["live_modified"] is False
    result=owner.activate()
    assert result["status"]=="ORIGINAL_FOUNDER_SEO_TOOL_SUITE_V2_LIVE_VERIFIED"
    assert result["source_files_changed"]==2
    assert (live/".next/BUILD_ID").read_text()=="NEW"
    assert (live/owner.SEO).read_text()=="SEO unified command centre"
    assert (live/owner.WORKBENCH).read_text()=="interactive tool suite"
    assert (proposal.parent/"activation_backups/.next.original/BUILD_ID").read_text()=="OLD"
    assert (proposal.parent/"activation_backups/seo.page.original.tsx").read_text()=="SEO original"
    assert (proposal.parent/"activation_result.json").exists()
    assert any(c[:2]==("systemctl","restart") for c in commands)


def test_other_owner_changed_blocks_everything(tmp_path,monkeypatch):
    live,proposal,_,_=configured(tmp_path,monkeypatch)
    name=next(iter(owner.OWNER_HASHES))
    (live/name).write_text("changed by another owner")
    with pytest.raises(owner.SEOReleaseHeld,match="UNRELATED_FOUNDER_OWNER_SOURCE_MISMATCH"):
        owner.activate()
    assert not (live/owner.WORKBENCH).exists()
    assert (live/".next/BUILD_ID").read_text()=="OLD"
    assert not (proposal.parent/"activation_backups").exists()


def test_restart_failure_restores_original_page_and_build(tmp_path,monkeypatch):
    live,proposal,_,command=configured(tmp_path,monkeypatch)
    attempts=[]
    def fail_first(*parts):
        if parts[:2]==("systemctl","restart"):
            attempts.append(parts)
            if len(attempts)==1:
                raise RuntimeError("simulated restart failed")
            return ""
        return command(*parts)
    monkeypatch.setattr(owner,"cmd",fail_first)
    with pytest.raises(RuntimeError,match="simulated restart"):
        owner.activate()
    assert (live/".next/BUILD_ID").read_text()=="OLD"
    assert (live/owner.SEO).read_text()=="SEO original"
    assert not (live/owner.WORKBENCH).exists()
    assert not (proposal.parent/"activation_result.json").exists()
    assert len(attempts)==2
