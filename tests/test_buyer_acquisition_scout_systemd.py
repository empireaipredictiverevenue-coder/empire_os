from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_buyer_scout_service_is_bounded_observe_only():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "run_buyer_acquisition_scout.py" in text
    assert "--max-queries 30" in text
    assert "--max-domains 50" in text
    assert "--max-probes 24" in text
    assert "ProtectSystem=strict" in text
    assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_buyer_scout_timer_is_not_high_frequency():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.timer"
    ).read_text()

    assert "OnUnitInactiveSec=30min" in text
    assert "Persistent=true" in text


def test_buyer_scout_service_persists_only_to_holding_area():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "reconcile_buyer_acquisition_scout.py" in text
    assert "persist_buyer_scout_candidates.py" in text
    assert "outbound_governor" not in text


def test_buyer_scout_service_materializes_review_readiness():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "materialize_buyer_scout_review_readiness.py" in text
    assert "persist_buyer_scout_candidates.py" in text


def test_buyer_scout_service_builds_non_mutating_promotion_plan():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    assert "build_buyer_scout_promotion_plan.py" in text


def test_buyer_scout_service_labels_pipeline_stages():
    text = (
        ROOT / "deploy/systemd/empire-buyer-acquisition-scout.service"
    ).read_text()

    for stage in (
        "DISCOVER + PROBE",
        "RECONCILE",
        "PERSIST HOLDING AREA",
        "REVIEW READINESS",
        "PROMOTION PLAN",
    ):
        assert stage in text


def test_opportunity_validation_seed_materializer_preserves_target(monkeypatch):
    from scripts.run_buyer_acquisition_scout import (
        _opportunity_validation_seed_records,
    )

    seen = []

    def fake_request(method, path):
        seen.append((method, path))
        return [{
            "id": "prospect-1",
            "business_name": "Denver Roofing Co",
            "niche": "roofing",
            "website": "https://denver-roofing.example",
            "metro": "Denver, CO",
            "status": "qualified",
            "created_at": "2026-09-26T12:00:00+00:00",
        }]

    monkeypatch.setattr(
        "scripts.run_buyer_acquisition_scout.request_json",
        fake_request,
    )

    plan = {
        "opportunity_validation": {
            "targets": [{
                "opportunity_key": "market:roofing:denver, co",
                "niche_family": "roofing",
                "territory": "denver, co",
                "corridor_key": (
                    "opportunity-validation:v1:roofing:denver_co"
                ),
                "product_code": None,
            }],
        },
    }

    rows = _opportunity_validation_seed_records(
        plan,
        per_target=4,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "prospect-1"
    assert row["seed_opportunity_key"] == "market:roofing:denver, co"
    assert row["seed_corridor_key"] == (
        "opportunity-validation:v1:roofing:denver_co"
    )
    assert row["seed_buyer_pools"] == [
        "end_service_buyers",
        "local_and_smb_buyers",
    ]
    assert row["icp_profile_key"] == "high_ticket_home_service"
    assert seen and seen[0][0] == "GET"
    assert "niche=eq.roofing" in seen[0][1]
    assert "metro=ilike.%2Adenver%2A" in seen[0][1]


def test_opportunity_seed_materializer_surfaces_query_error():
    from scripts.run_buyer_acquisition_scout import (
        _opportunity_validation_seed_records,
    )

    diagnostics = []

    def blocked(*_args, **_kwargs):
        raise RuntimeError(
            "Supabase egress circuit open locally; "
            "probe reserved for dedicated egress guard"
        )

    rows = _opportunity_validation_seed_records(
        {
            "opportunity_validation": {
                "targets": [{
                    "opportunity_key": "market:solar:united kingdom",
                    "niche_family": "solar",
                    "territory": "united kingdom",
                }],
            },
        },
        request=blocked,
        diagnostics=diagnostics,
    )

    assert rows == []
    assert len(diagnostics) == 1
    assert diagnostics[0]["state"] == "ERROR"
    assert diagnostics[0]["row_count"] == 0
    assert "egress circuit open locally" in diagnostics[0]["error"]


def test_legacy_canonical_seed_helper_does_not_use_opportunity_diagnostics(
    monkeypatch,
):
    import scripts.run_buyer_acquisition_scout as runner

    monkeypatch.setattr(
        runner,
        "request_json",
        lambda *_args, **_kwargs: [],
    )

    assert runner._canonical_seed_records(per_lane=1) == []


def test_local_opportunity_seed_recovery_snapshot_is_bounded(tmp_path):
    import json

    from scripts.run_buyer_acquisition_scout import (
        _local_opportunity_seed_records,
    )

    path = (
        tmp_path
        / "runtime/buyer_acquisition/opportunity_seed_recovery.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "mode": "OBSERVE",
            "seeds": [
                {
                    "id": "prospect-1",
                    "business_name": "Real Solar Ltd",
                    "niche": "solar",
                    "metro": "united kingdom",
                    "website": "https://real-solar.example",
                    "seed_opportunity_key": (
                        "market:solar:united kingdom"
                    ),
                    "seed_buyer_pools": [
                        "end_service_buyers",
                        "local_and_smb_buyers",
                    ],
                },
                {
                    "id": "missing-opportunity",
                    "website": "https://ignored.example",
                },
            ],
        }),
        encoding="utf-8",
    )

    rows = _local_opportunity_seed_records(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "prospect-1"
    assert row["seed_opportunity_key"] == (
        "market:solar:united kingdom"
    )
    assert row["recovery_source"] == "admin_read_only_snapshot"
    assert row["database_write_performed"] is False
    assert row["outbound_authorized"] is False



def test_recovery_snapshot_refresh_is_atomic_and_empty_safe(tmp_path):
    import json

    from scripts.run_buyer_acquisition_scout import (
        _write_local_opportunity_seed_snapshot,
    )

    row = {
        "id": "prospect-1",
        "business_name": "Roof Co",
        "niche": "roofing",
        "metro": "denver, co",
        "website": "https://roof.example",
        "seed_opportunity_key": "market:roofing:denver, co",
        "seed_buyer_pools": ["end_service_buyers"],
    }

    path = _write_local_opportunity_seed_snapshot(
        tmp_path,
        [row],
    )

    assert path is not None
    payload = json.loads(path.read_text())
    assert payload["mode"] == "OBSERVE"
    assert payload["database_write_performed"] is False
    assert payload["outbound_authorized"] is False
    assert payload["source"] == "canonical_rest_refresh"
    assert payload["seeds"][0]["id"] == "prospect-1"

    before = path.read_text()
    assert (
        _write_local_opportunity_seed_snapshot(
            tmp_path,
            [],
        )
        is None
    )
    assert path.read_text() == before
