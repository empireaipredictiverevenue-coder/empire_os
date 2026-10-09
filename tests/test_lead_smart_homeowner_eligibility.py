from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from empire_os.lead_smart_homeowner_eligibility import (
    PreviewEvidenceError,
    buyer_hours_preview,
    generate_from_files,
    make_public_zip_preview,
)
from scripts import materialize_lead_smart_roofing_preview as materializer


NOW = datetime(2026, 10, 9, 17, 50, tzinfo=timezone.utc)


def example():
    snapshot = {
        "schema_version": "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "observed_at": "2026-10-09T16:02:40+00:00",
        "source_hash": "source-sha",
        "coverage": {"row_count": 2, "unique_zip_count": 2},
        "rows": [
            {"zip": "00501", "top_payout": 75.25, "offer_name": "roofing"},
            {"zip": "07728", "top_payout": 15.0, "offer_name": "roofing"},
        ],
    }
    activation = {
        "schema_version": "empire.lead_smart.zip_targeting_gate.v1",
        "mode": "PREACTIVATION",
        "source_hash": "source-sha",
        "source_observed_at": snapshot["observed_at"],
        "zip_targeting_gate_verified": True,
        "zip_coverage_activation_verified": True,
        "source_fresh_for_targeting": True,
        "zip_count": 2,
        "verified_freshness": {
            "source_newest_last_updated": "2026-10-09T14:00:42+00:00",
        },
        "evidence_refs": {
            "coverage_snapshot": "sha256:snapshot",
            "coverage_intelligence": "sha256:intelligence",
        },
    }
    return snapshot, activation


def preview(snapshot=None, activation=None, *, now=NOW):
    snap, gate = example()
    return make_public_zip_preview(
        snapshot if snapshot is not None else snap,
        activation if activation is not None else gate,
        snapshot_sha256="snapshot",
        intelligence_sha256="intelligence",
        now=now,
    )


def test_sanitized_preview_contains_zips_but_not_payouts_or_call_authority():
    result = preview()
    assert result["covered_zips"] == ["00501", "07728"]
    assert result["count"] == 2
    assert result["call_authorized"] is False
    assert result["execution_authority"] == "NONE"
    text = json.dumps(result)
    assert "75.25" not in text and "15.0" not in text
    assert "+18883579305" not in text
    assert "2026-10-09T18:50:00+00:00" == result["expires_at"]


@pytest.mark.parametrize("change", [
    {"zip_targeting_gate_verified": False},
    {"zip_coverage_activation_verified": False},
    {"source_fresh_for_targeting": False},
    {"source_hash": "changed"},
    {"zip_count": 42},
    {"evidence_refs": {"coverage_snapshot": "sha256:wrong"}},
])
def test_invalid_gate_rejects_public_manifest(change):
    snapshot, gate = example()
    gate.update(change)
    with pytest.raises(PreviewEvidenceError):
        preview(snapshot, gate)


def test_stale_and_future_coverage_rejected():
    snapshot, gate = example()
    for stamp in ("2026-10-08T00:00:00+00:00", "2026-10-10T00:00:00+00:00"):
        snapshot["observed_at"] = stamp
        gate["source_observed_at"] = stamp
        with pytest.raises(PreviewEvidenceError, match="expired"):
            preview(snapshot, gate)


def test_duplicate_and_invalid_zip_rows_rejected():
    snapshot, gate = example()
    snapshot["rows"][1]["zip"] = "00501"
    with pytest.raises(PreviewEvidenceError, match="duplicate"):
        preview(snapshot, gate)
    snapshot["rows"][1]["zip"] = "1234"
    with pytest.raises(PreviewEvidenceError, match="invalid ZIP"):
        preview(snapshot, gate)


def test_generate_from_files_validates_actual_hashes(tmp_path):
    snapshot, gate = example()
    s = tmp_path / "snapshot.json"
    a = tmp_path / "activation.json"
    i = tmp_path / "intelligence.json"
    s.write_text(json.dumps(snapshot))
    i.write_text("{}")
    gate["evidence_refs"] = {
        "coverage_snapshot": "sha256:" + sha256(s.read_bytes()).hexdigest(),
        "coverage_intelligence": "sha256:" + sha256(i.read_bytes()).hexdigest(),
    }
    a.write_text(json.dumps(gate))
    result = generate_from_files(s, a, i, now=NOW)
    assert result["count"] == 2
    s.write_text(s.read_text() + " ")
    with pytest.raises(PreviewEvidenceError, match="does not match"):
        generate_from_files(s, a, i, now=NOW)


def test_materializer_default_is_check_only(tmp_path, monkeypatch, capsys):
    snapshot, gate = example()
    root = tmp_path / "runtime"
    (root / "coverage").mkdir(parents=True)
    s = root / "coverage/latest.json"
    a = root / "coverage/activation/latest.json"
    i = root / "coverage/intelligence/latest.json"
    a.parent.mkdir()
    i.parent.mkdir()
    s.write_text(json.dumps(snapshot))
    i.write_text("{}")
    gate["evidence_refs"] = {
        "coverage_snapshot": "sha256:" + sha256(s.read_bytes()).hexdigest(),
        "coverage_intelligence": "sha256:" + sha256(i.read_bytes()).hexdigest(),
    }
    a.write_text(json.dumps(gate))
    monkeypatch.setattr(materializer, "ROOT", root)
    monkeypatch.setattr(
        "sys.argv", ["script", "--out", str(tmp_path / "public" / "roofing-coverage.json")]
    )
    # Avoid depending on wall clock for fixture expiration.
    original = materializer.generate_from_files
    monkeypatch.setattr(materializer, "generate_from_files",
                        lambda s, a, i: original(s, a, i, now=NOW))
    assert materializer.main() == 0
    assert not (tmp_path / "public" / "roofing-coverage.json").exists()
    info = json.loads(capsys.readouterr().out)
    assert info["website_deployed"] is False
    assert info["call_authorized"] is False

    monkeypatch.setattr(
        "sys.argv", ["script", "--write", "--out",
                     str(tmp_path / "public" / "roofing-coverage.json")]
    )
    assert materializer.main() == 0
    path = tmp_path / "public" / "roofing-coverage.json"
    assert json.loads(path.read_text())["count"] == 2
    assert json.loads(capsys.readouterr().out)["execution_authority"] == "NONE"


@pytest.mark.parametrize(("when", "expected"), [
    ("2026-01-12T14:00:00+00:00", True),   # Monday, 8am CST
    ("2026-01-12T13:59:00+00:00", False),
    ("2026-07-06T13:00:00+00:00", True),   # Monday, 8am CDT
    ("2026-07-05T14:59:00+00:00", False),  # Sunday, 9:59 CDT
    ("2026-07-05T15:00:00+00:00", True),
    ("2026-07-05T21:00:00+00:00", False),
])
def test_buyer_hour_preview_handles_central_time_dst_without_call_authority(
    when, expected,
):
    now = datetime.fromisoformat(when)
    result = buyer_hours_preview(now=now)
    assert result["within_reported_window"] is expected
    assert result["timezone_interpretation_verified"] is False
    assert result["call_authorized"] is False
