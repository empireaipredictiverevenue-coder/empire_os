import json

from empire_os.founder_ops_api import read_ops_snapshot


def test_missing_snapshot_is_explicit(tmp_path):
    payload = read_ops_snapshot(tmp_path / "missing.json")
    assert payload["available"] is False
    assert payload["healthy"] is None


def test_snapshot_is_exposed_without_mutation(tmp_path):
    path = tmp_path / "latest.json"
    expected = {
        "schema_version": "empire.ops_control_cycle.v1",
        "healthy": True,
        "business_blocker": "buyer_conversation",
        "healer": {"proposed": 0, "executed": 0, "results": []},
        "sentinel": {"findings": [], "repair_plan": []},
    }
    path.write_text(json.dumps(expected))
    payload = read_ops_snapshot(path)
    assert payload["available"] is True
    assert payload["business_blocker"] == "buyer_conversation"
    assert payload["healthy"] is True
