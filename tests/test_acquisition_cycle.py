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
