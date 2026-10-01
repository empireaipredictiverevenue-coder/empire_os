from empire_os.aeo_recovery import audit_aeo_asset, build_aeo_recovery_census


def write_page(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


BASE = """<html><head>
<title>Roofing Dallas</title>
<meta name="description" content="Observed local roofing intelligence">
<link rel="canonical" href="https://example.com/roofing/DFW">
<script type="application/ld+json">{{}}</script>
</head><body><h1>Roofing Dallas</h1><p>{text}</p></body></html>"""


def test_supported_structure_can_reach_evidence_review(tmp_path):
    path = tmp_path / "roofing" / "DFW" / "index.html"
    write_page(path, BASE.format(text="Evidence based local information. " * 40))
    result = audit_aeo_asset(path, root=tmp_path)
    assert result.status == "structure_ready_for_evidence_review"
    assert result.publish_allowed is False


def test_unsupported_legacy_claim_blocks_recovery(tmp_path):
    path = tmp_path / "roofing" / "DFW" / "index.html"
    write_page(path, BASE.format(text="142 leads today. Updated every 6 hours. $240/mo."))
    result = audit_aeo_asset(path, root=tmp_path)
    assert result.status == "blocked_for_rewrite"
    assert "dynamic_lead_count_claim" in result.risk_flags
    assert "update_frequency_claim" in result.risk_flags
    assert "unverified_fixed_price" in result.risk_flags


def test_census_counts_assets_and_risks(tmp_path):
    write_page(
        tmp_path / "roofing" / "DFW" / "index.html",
        BASE.format(text="Observed evidence. " * 40),
    )
    write_page(
        tmp_path / "hvac" / "DFW" / "index.html",
        BASE.format(text="Exclusive leads within the hour."),
    )
    result = build_aeo_recovery_census(tmp_path)
    assert result["asset_count"] == 2
    assert result["niche_count"] == 2
    assert result["publishing_authority"] is False
    assert result["status_counts"]["blocked_for_rewrite"] == 1


def test_producer_writes_timezone_aware_census(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone
    from scripts import build_aeo_recovery_snapshot as producer

    write_page(tmp_path / "pages/roofing/DFW/index.html", BASE.format(text="Evidence. " * 100))
    monkeypatch.setattr(producer, "ROOT", tmp_path / "pages")
    monkeypatch.setattr(producer, "OUTPUT", tmp_path / "snapshot.json")
    before = datetime.now(timezone.utc)
    assert producer.main() == 0
    payload = json.loads(producer.OUTPUT.read_text())
    stamp = datetime.fromisoformat(payload["generated_at"])
    assert stamp.tzinfo is not None
    assert before <= stamp <= datetime.now(timezone.utc)
    assert payload["asset_count"] == 1


def test_missing_asset_root_fails_closed(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="aeo_asset_root_unavailable"):
        build_aeo_recovery_census(tmp_path / "missing")
