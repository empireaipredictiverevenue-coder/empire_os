from pathlib import Path
from unittest.mock import patch

import scripts.run_acquisition_cycle as cycle


def test_cycle_rotates_real_metros_without_outreach(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path/"state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path/"latest.json")
    monkeypatch.setattr(cycle, "LAST_SUCCESS", tmp_path/"last_success.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path/"cycle.lock")

    class Done:
        returncode=0
        stdout='{"msg": "prospect_acquired"}\n{"msg":"crawler_run_done","accepted":3}'
        stderr=''

    with patch.object(cycle.subprocess, "run", return_value=Done()) as run:
        result=cycle.run_cycle(max_candidates=5)

    assert result["ok"] is True
    assert result["real_data_only"] is True
    assert result["outreach_enabled"] is False
    command=run.call_args.args[0]
    assert "overpass" in command
    assert "--max-candidates" in command
    assert (tmp_path/"state.json").exists()
    assert (tmp_path/"last_success.json").exists()


def test_cycle_rejects_unbounded_batch():
    try:
        cycle.run_cycle(max_candidates=1000)
    except ValueError as exc:
        assert "between 1 and 25" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cycle_rotates_after_failed_source_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path / "latest.json")
    monkeypatch.setattr(cycle, "LAST_SUCCESS", tmp_path / "last_success.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path / "cycle.lock")

    class Failed:
        returncode = 1
        stdout = ''
        stderr = 'source unavailable'

    with patch.object(cycle.subprocess, "run", return_value=Failed()):
        first = cycle.run_cycle(max_candidates=5)

    assert first["ok"] is False
    state = __import__("json").loads((tmp_path / "state.json").read_text())
    assert state["last_metro"] == list(cycle.METRO_COORDS)[0]
    assert state["last_ok"] is False
    assert state["next_index"] == 1



def test_cycle_can_be_scoped_to_one_country(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path / "latest.json")
    monkeypatch.setattr(cycle, "LAST_SUCCESS", tmp_path / "last_success.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path / "cycle.lock")
    monkeypatch.setenv("EMPIRE_ACQUISITION_COUNTRIES", "GB")

    class Done:
        returncode = 0
        stdout = '{"msg": "prospect_acquired"}'
        stderr = ""

    with patch.object(cycle.subprocess, "run", return_value=Done()):
        result = cycle.run_cycle(max_candidates=5)

    assert result["country_code"] == "GB"
    assert result["geo_country_scope"] == ["GB"]



def test_legacy_soak_market_set_preserves_round_robin(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path / "latest.json")
    monkeypatch.setattr(cycle, "LAST_SUCCESS", tmp_path / "last_success.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path / "cycle.lock")
    monkeypatch.setenv("EMPIRE_ACQUISITION_MARKET_SET", "legacy_us")
    monkeypatch.setenv("EMPIRE_ACQUISITION_COUNTRIES", "US")

    class Done:
        returncode = 0
        stdout = '{"msg": "prospect_acquired"}'
        stderr = ""

    with patch.object(cycle.subprocess, "run", return_value=Done()):
        result = cycle.run_cycle(max_candidates=5)

    assert result["metro"] == "Houston, TX"
    assert result["geo_policy"] == "legacy_round_robin"
    assert result["geo_market_set"] == "legacy_us"



def test_signal_success_reports_runtime_inbox_not_supabase(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path / "latest.json")
    monkeypatch.setattr(cycle, "LAST_SUCCESS", tmp_path / "last_success.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path / "cycle.lock")

    class Done:
        returncode = 0
        stdout = '{"msg": "signal_queued"}'
        stderr = ""

    with patch.object(cycle.subprocess, "run", return_value=Done()):
        result = cycle.run_cycle(max_candidates=5)

    assert result["prospect_canonical_write"] is False
    assert result["signal_inbox_write"] is True
    assert result["canonical_store"] == "runtime_signal_inbox"

    last_success = __import__("json").loads(
        (tmp_path / "last_success.json").read_text()
    )
    assert last_success["canonical_writes"] is False
    assert last_success["prospect_canonical_write"] is False
    assert last_success["signal_inbox_write"] is True
    assert last_success["write_store"] == "runtime_signal_inbox"
