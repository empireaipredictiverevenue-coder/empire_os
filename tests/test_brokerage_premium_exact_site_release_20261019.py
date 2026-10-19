"""Byte-pinned, additive commercial page release — simulated install only."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import pytest

HERE=Path(__file__).resolve().parents[1]
MODULE=HERE/"scripts/release_brokerage_premium_commercial_assets_20261019.py"
spec=importlib.util.spec_from_file_location("premium_static_release",MODULE)
assert spec is not None and spec.loader is not None
import sys
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

LIVE=Path("/home/ubuntu/empire_worktrees/flagship_organic_collector_merged_20261018/apps/empire-public-site/out")
STAGED=module.STAGED

def stage_fake(tmp):
    root=tmp/"out"
    (root/"_next/static").mkdir(parents=True)
    shutil.copy2(LIVE/"commercial.html",root/"commercial.html")
    original=LIVE/"_next/static"
    for path in original.rglob("*"):
        if path.is_file():
            r=path.relative_to(original);dst=root/"_next/static"/r
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,dst)
    return root

def test_original_and_exact_candidate_match_all_rendered_text():
    p=module.plan(LIVE,STAGED)
    assert module.digest(p.baseline)==module.EXPECTED_OLD
    assert module.digest(p.candidate)==module.EXPECTED_NEW
    assert len(p.added)==11
    assert "page-" in p.new_page_js

def test_cannot_apply_over_a_drifted_production_html(tmp_path):
    root=stage_fake(tmp_path)
    (root/"commercial.html").write_bytes(b"Other ASTRA update")
    with pytest.raises(ValueError,match="LIVE_COMMERCIAL_HTML_CHANGED"):
        module.plan(root,STAGED)

def test_static_artifact_collision_fails_without_overwrite(tmp_path):
    root=stage_fake(tmp_path)
    p=module.plan(root,STAGED)
    collision=root/"_next/static"/p.added[0]
    collision.parent.mkdir(parents=True,exist_ok=True)
    collision.write_bytes(b"OTHER_AGENT_JS")
    with pytest.raises(ValueError,match="EXISTING_SHARED_STATIC_ASSET_CONFLICT"):
        module.plan(root,STAGED)
    assert collision.read_bytes()==b"OTHER_AGENT_JS"

def test_simulated_full_static_release_has_restore_copy_and_only_new_assets(tmp_path):
    root=stage_fake(tmp_path)
    baseline=root/"commercial.html"
    before=baseline.read_bytes()
    p=module.plan(root,STAGED)
    report=module.install(p,live=root,staged=STAGED,backup=tmp_path/"rollback")
    assert report["status"]=="SURGICAL_BROKERAGE_PREMIUM_COMMERCIAL_HTML_PUBLISHED"
    assert report["site_other_pages_changed"] is False
    assert report["outbound_sent"] is False
    assert report["public_premium_api_activated"] is False
    assert module.digest(baseline.read_bytes())==module.EXPECTED_NEW
    assert any((tmp_path/"rollback").glob("commercial-*.html"))
    assert next((tmp_path/"rollback").glob("commercial-*.html")).read_bytes()==before
    for rel in p.added:
        assert (root/"_next/static"/rel).read_bytes()==(STAGED/"_next/static"/rel).read_bytes()
    with pytest.raises(ValueError,match="LIVE_COMMERCIAL_HTML_CHANGED"):
        module.plan(root,STAGED)
