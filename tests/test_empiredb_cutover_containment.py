from pathlib import Path

import empire_os.supabase_egress_guard as guard


def test_supabase_guard_is_inert_under_empiredb(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv(
        "EMPIRE_DATA_BACKEND",
        "empiredb",
    )
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "guard.json",
    )

    def forbidden_request(*args, **kwargs):
        raise AssertionError(
            "Supabase must not be probed under EmpireDB"
        )

    def forbidden_systemctl(*args, **kwargs):
        raise AssertionError(
            "EmpireDB services must not be contained"
        )

    result = guard.run_guard(
        request=forbidden_request,
        run=forbidden_systemctl,
        stagger_seconds=0,
    )

    assert result["state"] == "inactive_empiredb"
    assert result["contained"] is False
    assert result["canonical_backend"] == "empiredb"
    assert result["managed_timers"] == []


def test_legacy_lane_leads_not_materialized_into_empiredb():
    source = Path(
        "scripts/run_legacy_permit_recovery_observer.py"
    ).read_text()

    assert "LEGACY_SOURCE_UNAVAILABLE" in source
    assert (
        "legacy_supabase.public.lane_leads"
        in source
    )


def test_guard_wrapper_accepts_inactive_empiredb():
    source = Path(
        "scripts/run_supabase_egress_guard.py"
    ).read_text()

    assert '"inactive_empiredb"' in source
    assert "SUCCESS_STATES" in source
