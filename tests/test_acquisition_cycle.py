from pathlib import Path
from unittest.mock import patch

import scripts.run_acquisition_cycle as cycle


def test_cycle_rotates_real_metros_without_outreach(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "RUNTIME", tmp_path)
    monkeypatch.setattr(cycle, "STATE", tmp_path/"state.json")
    monkeypatch.setattr(cycle, "LATEST", tmp_path/"latest.json")
    monkeypatch.setattr(cycle, "LOCK", tmp_path/"cycle.lock")

    class Done:
        returncode=0
        stdout='{"msg":"crawler_run_done","accepted":3}'
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


def test_cycle_rejects_unbounded_batch():
    try:
        cycle.run_cycle(max_candidates=1000)
    except ValueError as exc:
        assert "between 1 and 25" in str(exc)
    else:
        raise AssertionError("expected ValueError")
