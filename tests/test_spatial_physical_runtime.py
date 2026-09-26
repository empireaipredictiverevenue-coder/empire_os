import json

from empire_os.spatial_physical_runtime import build_spatial_physical_runtime


def test_runtime_projection_reads_real_storm_exposure_and_preserves_unknown_3d(tmp_path):
    root = tmp_path / "repo"
    strike_dir = root / "runtime" / "revenue_strike"
    feedback_dir = root / "runtime" / "feedback"
    strike_dir.mkdir(parents=True)
    feedback_dir.mkdir(parents=True)

    (strike_dir / "dfw.json").write_text(json.dumps({
        "execution_authority": "none",
        "market": "Dallas-Fort Worth, TX",
        "observed_at": "2026-09-20T22:50:00Z",
        "trigger": {
            "source": "NWS Dallas/Fort Worth Area Forecast Discussion",
            "modeled_multiplier": 2.454,
            "modeled_only": True,
        },
    }))
    (feedback_dir / "satellite_damage.jsonl").write_text(
        json.dumps({
            "ts": "2026-09-16T21:54:13Z",
            "level": "WARN",
            "msg": "scan_blocked_no_real_imagery",
        }) + "\n"
    )

    payload = build_spatial_physical_runtime(root)
    assert payload["mode"] == "OBSERVE"
    assert payload["execution_authority"] == "none"
    assert payload["physical_observations"] == 1
    assert payload["volumetric_observations"] is None
    assert payload["modeled_opportunities"] is None
    assert payload["storm_multiplier_max"] == 2.454
    assert payload["source_state"]["satellite_real_imagery"] is False
    assert payload["unknown_stays_unknown"] is True


def test_runtime_projection_does_not_count_invalid_or_authorized_mutating_rows(tmp_path):
    root = tmp_path / "repo"
    strike_dir = root / "runtime" / "revenue_strike"
    strike_dir.mkdir(parents=True)

    (strike_dir / "bad.json").write_text(json.dumps({
        "execution_authority": "execute",
        "observed_at": "2026-09-20T22:50:00Z",
        "trigger": {
            "source": "NWS",
            "modeled_multiplier": 2.0,
        },
    }))

    payload = build_spatial_physical_runtime(root)
    assert payload["physical_observations"] is None
    assert payload["evidence_refs"] == []
