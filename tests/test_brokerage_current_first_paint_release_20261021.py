"""Current V2 premium brokerage first-paint atomic release safety regression."""
from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from scripts import release_brokerage_current_first_paint_20261021 as release


def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    live = tmp_path / "live"
    live.mkdir()
    (live / "commercial.html").write_bytes(
        (release.LIVE / "commercial.html").read_bytes()
    )
    statics = release.STAGED / "_next/static"
    live_static = live / "_next/static"
    for file in statics.rglob("*"):
        if not file.is_file():
            continue
        rel = file.relative_to(statics)
        if (release.LIVE / "_next/static" / rel).is_file():
            dest = live_static / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest)
    return live, release.STAGED


def test_exact_current_public_baseline_preflight():
    p = release.inspect()
    assert release.digest(p.old) == release.OLD_SHA
    assert release.digest(p.new) == release.NEW_SHA
    assert len(p.added) == 13
    assert sum((release.STAGED / "_next/static" / x).stat().st_size
               for x in p.added) == 315856


def test_sandbox_atomic_release_and_rollback(tmp_path):
    live, stage = sandbox(tmp_path)
    p = release.inspect(live, stage)
    records = tmp_path / "secure-receipts"
    result = release.publish(p, live=live, stage=stage, receipts=records)
    assert result["status"] == "BROKERAGE_CURRENT_FIRST_PAINT_PAGE_PUBLISHED"
    assert release.digest((live / "commercial.html").read_bytes()) == release.NEW_SHA
    rollback = Path(result["rollback_file"])
    assert rollback.read_bytes() == p.old
    assert rollback.stat().st_mode & 0o777 == 0o600
    assert result["new_static_assets"] == 13
    assert result["other_pages_mutated"] is False
    assert result["services_restarted"] is False
    assert result["outbound_sent"] is False
    assert result["database_writes"] is False
    assert result["payments_changed"] is False
    assert result["first_real_enquiry_verified"] is False
    verified = release.verify_live(live, stage)
    assert verified["two_services_visible_in_initial_html"] is True
    assert verified["matched_static_assets"] == 41


def test_changed_live_html_aborts_before_any_write(tmp_path):
    live, stage = sandbox(tmp_path)
    existing = (live / "commercial.html").read_bytes()
    (live / "commercial.html").write_bytes(existing + b"other-owner-update")
    with pytest.raises(ValueError, match="CONCURRENT_LIVE_COMMERCIAL_PAGE_CHANGED"):
        release.inspect(live, stage)
    assert not (tmp_path / "secure-receipts").exists()


def test_different_existing_shared_asset_refuses_publish(tmp_path):
    live, stage = sandbox(tmp_path)
    p = release.inspect(live, stage)
    target = live / "_next/static" / p.added[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"competing website owner asset")
    with pytest.raises(ValueError, match="EXISTING_SHARED_ASSET_CHANGED"):
        release.inspect(live, stage)


def test_second_release_attempt_does_not_overwrite_live_or_backup(tmp_path):
    live, stage = sandbox(tmp_path)
    p = release.inspect(live, stage)
    receipts = tmp_path / "secure-receipts"
    release.publish(p, live=live, stage=stage, receipts=receipts)
    with pytest.raises(ValueError, match="CONCURRENT_LIVE_COMMERCIAL_PAGE_CHANGED"):
        release.inspect(live, stage)
