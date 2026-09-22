from empire_os.voice_routing_policy import (
    should_route_to_switchboard,
    switchboard_status,
)


def test_ppc_switchboard_is_parked_by_default(monkeypatch):
    monkeypatch.delenv("EMPIRE_PPC_SWITCHBOARD_MODE", raising=False)
    monkeypatch.delenv(
        "EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED",
        raising=False,
    )
    status = switchboard_status()
    assert status["mode"] == "PARKED"
    assert status["route_enabled"] is False
    assert status["execution_allowed"] is False
    assert status["canonical_transport"] == "vonage"
    assert status["canonical_database"] == "supabase"
    assert status["canonical_payment_rail"] == "usdt_bsc"
    assert should_route_to_switchboard() is False


def test_switchboard_needs_both_active_mode_and_route_gate(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "ACTIVE")
    monkeypatch.setenv(
        "EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED",
        "false",
    )
    assert should_route_to_switchboard() is False

    monkeypatch.setenv(
        "EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED",
        "true",
    )
    assert should_route_to_switchboard() is True
