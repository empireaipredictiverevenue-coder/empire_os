from empire_os.control_fabric_snapshot import build_control_fabric_snapshot


def test_snapshot_is_observe_only_and_contains_registry():
    result = build_control_fabric_snapshot()
    assert result["mode"] == "OBSERVE"
    assert result["execution_authority"] == "none"
    assert result["component_count"] >= 10
    assert result["external_execution_enabled"] is False
    assert result["founder_gates_preserved"] is True
    assert "buyer_reply_received" in result["event_routes"]
    assert "conversation_os" in result["event_routes"]["buyer_reply_received"]
