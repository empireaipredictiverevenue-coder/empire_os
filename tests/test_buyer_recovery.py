from pathlib import Path

import empire_os.buyer_recovery as buyer_recovery


def _plan():
    return {
        "opportunity_validation": {
            "targets": [{
                "opportunity_key": "market:roofing:denver, co",
                "niche_family": "roofing",
                "territory": "denver, co",
                "corridor_key": "opportunity-validation:v1:roofing:denver_co",
                "product_code": None,
            }],
        },
    }


def test_snapshot_preserves_last_known_good_when_refresh_is_empty(tmp_path):
    original = [{
        "id": "p1",
        "business_name": "Roof Co",
        "niche": "roofing",
        "metro": "denver, co",
        "website": "https://roof.example",
        "seed_opportunity_key": "market:roofing:denver, co",
    }]

    path = buyer_recovery.write_local_recovery_snapshot(
        tmp_path,
        original,
    )
    assert path is not None
    before = path.read_text()

    assert (
        buyer_recovery.write_local_recovery_snapshot(
            tmp_path,
            [],
        )
        is None
    )
    assert path.read_text() == before


def test_query_seed_failure_is_diagnostic_and_non_destructive(tmp_path):
    root = Path(tmp_path)
    plan_path = root / "runtime/buyer_acquisition/latest.json"
    plan_path.parent.mkdir(parents=True)
    import json
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")

    buyer_recovery.write_local_recovery_snapshot(
        root,
        [{
            "id": "p1",
            "business_name": "Roof Co",
            "niche": "roofing",
            "metro": "denver, co",
            "website": "https://roof.example",
            "seed_opportunity_key": "market:roofing:denver, co",
        }],
    )
    snapshot = root / buyer_recovery.RECOVERY_SEED_SNAPSHOT
    before = snapshot.read_text()

    def blocked(*_args, **_kwargs):
        raise RuntimeError("Supabase egress circuit open locally")

    result = buyer_recovery.refresh_last_known_good_snapshot(
        root,
        request=blocked,
    )

    assert result["state"] == "PRESERVED_LAST_KNOWN_GOOD"
    assert result["query_error_count"] == 1
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert snapshot.read_text() == before


def test_local_recovery_disables_search_and_preserves_authority(
    monkeypatch,
    tmp_path,
):
    root = Path(tmp_path)
    guard = root / "runtime/control/supabase_egress_guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        '{"state":"contained","contained":true}',
        encoding="utf-8",
    )

    buyer_recovery.write_local_recovery_snapshot(
        root,
        [{
            "id": "p1",
            "business_name": "Roof Co",
            "niche": "roofing",
            "metro": "denver, co",
            "website": "https://roof.example",
            "seed_opportunity_key": "market:roofing:denver, co",
            "seed_buyer_pools": ["end_service_buyers"],
        }],
    )

    seen = {}

    def fake_refresh(repo_root, **kwargs):
        seen["root"] = Path(repo_root)
        seen.update(kwargs)
        return {
            "search_enabled": False,
            "opportunity_seed_domain_count": 1,
            "probed_domain_count": 1,
            "candidate_count": 1,
            "probe_failure_counts": {},
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }

    monkeypatch.setattr(
        buyer_recovery,
        "refresh_buyer_scout",
        fake_refresh,
    )

    result = buyer_recovery.run_local_buyer_recovery(root)

    assert result["state"] == "LOCAL_RECOVERY_EXECUTED"
    assert seen["search_enabled"] is False
    assert len(seen["canonical_seed_records"]) == 1
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_local_recovery_idles_when_guard_is_healthy(tmp_path):
    root = Path(tmp_path)
    guard = root / "runtime/control/supabase_egress_guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        '{"state":"healthy","contained":false}',
        encoding="utf-8",
    )

    result = buyer_recovery.run_local_buyer_recovery(root)

    assert result["state"] == "IDLE_GUARD_HEALTHY"
    assert result["contained"] is False
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
