from __future__ import annotations

import json
from pathlib import Path

from empire_os.organic_search_legacy_recovery import build_recovery_manifest


def _write_report(root: Path, assets: list[dict]) -> None:
    path = root / "runtime/search_intelligence/aeo_recovery/latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "asset_count": len(assets),
        "niche_count": len({a["niche"] for a in assets}),
        "metro_count": len({a["metro"] for a in assets}),
        "unique_content_hashes": len({a["content_hash"] for a in assets}),
        "risk_counts": {},
        "assets": assets,
    }))


def test_clean_assets_still_fail_closed_on_publish_and_capture(tmp_path: Path):
    _write_report(tmp_path, [{
        "niche": "roofing",
        "metro": "DFW",
        "content_hash": "a",
        "status": "structure_ready_for_evidence_review",
        "risk_flags": [],
        "publish_allowed": False,
        "form_present": False,
    }])
    result = build_recovery_manifest(tmp_path)
    organic = result["organic_search"]
    assert organic["state"] == "REVIEW_READY"
    assert organic["review_ready_count"] == 1
    assert organic["publish_allowed_count"] == 0
    assert "evidence_review_and_publish_authority" in organic["blockers"]
    assert "canonical_enquiry_capture" in organic["blockers"]
    assert result["execution_authority"] == "none"
    assert result["actions_performed"]["publish"] is False
    assert result["actions_performed"]["import_leads"] is False


def test_twenty_plugin_does_not_prove_data_or_migration(tmp_path: Path):
    _write_report(tmp_path, [])
    plugin = tmp_path / "twenty-crm.yaml"
    plugin.write_text("name: twenty-crm\n")
    result = build_recovery_manifest(tmp_path, twenty_plugin_path=plugin)
    twenty = result["legacy_marketing_sources"]["twenty"]
    assert twenty["plugin_definition_present"] is True
    assert twenty["local_runtime_data_proven"] is False
    assert twenty["migration_proven"] is False


def test_missing_report_stays_unknown(tmp_path: Path):
    result = build_recovery_manifest(tmp_path)
    assert result["organic_search"]["state"] == "UNKNOWN"
    assert result["organic_search"]["blockers"] == ["aeo_recovery_report_missing"]
