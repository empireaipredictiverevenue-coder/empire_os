"""Scope-constrained buyer HTML and hashed Next.js asset publication."""
from hashlib import sha256
from pathlib import Path
import json

import pytest

from scripts import promote_direct_bsc_buy_static_export as release


def test_default_off_and_exact_flag(capsys,monkeypatch):
    monkeypatch.setattr(release,"apply",lambda:pytest.fail("would write"))
    assert release.main([])==0
    for arg in (["--apply"],["--force"],
                ["--apply","--approved-direct-bsc-buyer-status-release-only"]):
        assert release.main(arg)==3
    assert "STAGED_NOT_APPLIED" in capsys.readouterr().out


def test_manifest_references_only_versioned_next_assets_and_buy_html(monkeypatch):
    monkeypatch.setattr(release,"_exact_git",lambda path:None)
    info,source,target=release._validated()
    assert source.name=="out"
    assert target.name=="out"
    assert 1<=len(info["assets"])<=150
    assert all(a["path"].startswith("_next/static/") for a in info["assets"])
    assert all(a["size"]>=0 for a in info["assets"])
    assert release.sha(source/"buy.html")==info["buy_sha256"]
    assert release.sha(target/"buy.html")==info["prior_live_buy_sha256"]
    assert info["buy_sha256"]!=info["prior_live_buy_sha256"]


def test_atomic_one_file_publisher_refuses_overwrite(tmp_path):
    src=tmp_path/"source.js"
    src.write_text("safe",encoding="utf-8")
    target=tmp_path/"dest"/"new.js"
    release._new_file(src,target)
    assert target.read_text()=="safe"
    assert target.stat().st_mode & 0o777==0o644
    with pytest.raises(ValueError):
        release._new_file(src,target)


def test_isolated_publisher_preserves_unrelated_export(tmp_path,monkeypatch):
    preview=tmp_path/"preview";live=tmp_path/"public"
    for path in (preview,live):
        (path/"_next"/"static"/"chunks").mkdir(parents=True)
    (preview/"buy.html").write_text("new buyer checkout page")
    (live/"buy.html").write_text("old buyer checkout page")
    (live/"industries.html").write_text("unchanged non-checkout page")
    asset=preview/"_next"/"static"/"chunks"/"new-built-version.js"
    asset.write_text("safe browser code")
    metadata={
      "buy_sha256":release.sha(preview/"buy.html"),
      "prior_live_buy_sha256":release.sha(live/"buy.html"),
      "assets":[{"path":"_next/static/chunks/new-built-version.js",
                 "sha256":release.sha(asset),"size":asset.stat().st_size}],
    }
    monkeypatch.setattr(release,"_validated",lambda:(metadata,preview,live))
    monkeypatch.setattr(release,"BACKUP",tmp_path/"backup")
    monkeypatch.setattr(release,"_serve_hash",lambda:metadata["buy_sha256"])
    result=release.apply()
    assert result["status"]=="CHECKOUT_BUY_STATIC_PAGE_RELEASE_VERIFIED"
    assert result["new_immutable_assets"]==1
    assert (live/"buy.html").read_text()=="new buyer checkout page"
    assert (live/"industries.html").read_text()=="unchanged non-checkout page"
    assert (tmp_path/"backup"/"buy.html").read_text()=="old buyer checkout page"


def test_bad_live_readback_rolls_back_only_buy_page(tmp_path,monkeypatch):
    preview=tmp_path/"preview";live=tmp_path/"public"
    preview.mkdir();live.mkdir()
    (preview/"buy.html").write_text("changed")
    (live/"buy.html").write_text("original")
    metadata={
      "buy_sha256":release.sha(preview/"buy.html"),
      "prior_live_buy_sha256":release.sha(live/"buy.html"),
      "assets":[],
    }
    monkeypatch.setattr(release,"_validated",lambda:(metadata,preview,live))
    monkeypatch.setattr(release,"BACKUP",tmp_path/"backup")
    monkeypatch.setattr(release,"_serve_hash",lambda:"0"*64)
    with pytest.raises(ValueError,match="readback"):
        release.apply()
    assert (live/"buy.html").read_text()=="original"


def test_publisher_never_restarts_services_or_touches_payments():
    code=Path(release.__file__).read_text()
    for forbidden in (
      "systemctl restart","systemctl daemon-reload",
      "INSERT INTO","UPDATE public.",
      "empiredb_migrator","wallet.private_key",
    ):
        assert forbidden not in code
    assert 'only_checkout_page_changed' in code
    assert '"database_writes":False' in code
