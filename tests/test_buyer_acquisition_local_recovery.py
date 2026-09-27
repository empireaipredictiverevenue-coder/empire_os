import json
from pathlib import Path

import scripts.run_buyer_acquisition_local_recovery as recovery


def _write_guard(root: Path, *, contained: bool) -> None:
    path = root / "runtime/control/supabase_egress_guard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "state": "contained" if contained else "healthy",
            "contained": contained,
        }),
        encoding="utf-8",
    )


def test_local_recovery_is_idle_when_guard_is_healthy(
    monkeypatch,
    tmp_path,
):
    _write_guard(tmp_path, contained=False)

    monkeypatch.setattr(
        recovery,
        "_local_opportunity_seed_records",
        lambda _root: (_ for _ in ()).throw(
            AssertionError("seeds must not load while guard is healthy")
        ),
    )

    payload = recovery.run_local_recovery(tmp_path)

    assert payload["state"] == "IDLE_GUARD_HEALTHY"
    assert payload["contained"] is False
    assert payload["database_write_performed"] is False
    assert payload["outbound_sent"] is False
    assert payload["execution_authority"] == "none"


def test_local_recovery_skips_search_and_stays_observe_only(
    monkeypatch,
    tmp_path,
):
    _write_guard(tmp_path, contained=True)

    seeds = [{
        "id": "seed-1",
        "business_name": "Recovered Roofing",
        "website": "https://roof.example",
        "seed_opportunity_key": "market:roofing:denver, co",
    }]
    monkeypatch.setattr(
        recovery,
        "_local_opportunity_seed_records",
        lambda _root: seeds,
    )

    seen = {}

    def fake_refresh(root, **kwargs):
        seen["root"] = Path(root)
        seen.update(kwargs)
        return {
            "candidate_count": 1,
            "opportunity_seed_domain_count": 1,
            "probe_failure_counts": {},
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }

    monkeypatch.setattr(recovery, "refresh_buyer_scout", fake_refresh)

    payload = recovery.run_local_recovery(tmp_path)

    assert payload["state"] == "LOCAL_RECOVERY_EXECUTED"
    assert payload["candidate_count"] == 1
    assert payload["seed_count"] == 1
    assert seen["search_enabled"] is False
    assert seen["canonical_seed_records"] == seeds
    assert seen["max_queries"] == 4
    assert seen["max_probes"] == 12
    assert payload["database_write_performed"] is False
    assert payload["outbound_sent"] is False
    assert payload["execution_authority"] == "none"


def test_local_recovery_noops_when_contained_without_snapshot(
    monkeypatch,
    tmp_path,
):
    _write_guard(tmp_path, contained=True)
    monkeypatch.setattr(
        recovery,
        "_local_opportunity_seed_records",
        lambda _root: [],
    )

    payload = recovery.run_local_recovery(tmp_path)

    assert payload["state"] == "CONTAINED_NO_RECOVERY_SEEDS"
    assert payload["candidate_count"] == 0


def test_local_recovery_systemd_unit_is_local_only():
    root = Path(__file__).resolve().parents[1]
    service = (
        root
        / "deploy/systemd/empire-buyer-acquisition-local-recovery.service"
    ).read_text()
    timer = (
        root
        / "deploy/systemd/empire-buyer-acquisition-local-recovery.timer"
    ).read_text()

    assert "run_buyer_acquisition_local_recovery.py" in service
    assert "persist_buyer_scout_candidates.py" not in service
    assert "reconcile_buyer_acquisition_scout.py" not in service
    assert "materialize_buyer_scout_review_readiness.py" not in service
    assert "build_buyer_scout_promotion_plan.py" not in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitInactiveSec=15min" in timer
