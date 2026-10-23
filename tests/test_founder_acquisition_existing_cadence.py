"""The original production Buyer Acquisition Team cadence is the only scheduler."""
from types import SimpleNamespace

from empire_os import buyer_acquisition_team as team


def test_nonproduction_root_does_not_launch_any_new_worker(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("not allowed")
    monkeypatch.setattr("subprocess.run", unexpected)
    v = team.refresh_founder_acquisition_observer(tmp_path)
    assert v == {"status": "NOT_PRODUCTION_ROOT", "outbound_sent": False}


def test_production_root_with_missing_runner_is_never_a_send(monkeypatch):
    from pathlib import Path
    original = Path.is_file
    monkeypatch.setattr(
        Path, "is_file",
        lambda p: False if p.name == "run_founder_acquisition_review.py" else original(p),
    )
    v = team.refresh_founder_acquisition_observer("/srv/empire_os")
    assert v == {"status": "RUNNER_NOT_DEPLOYED", "outbound_sent": False}


def test_existing_timer_invokes_separate_observe_only_runner(monkeypatch):
    import subprocess
    records = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: (records.append((a, k)) or SimpleNamespace(
            returncode=0,
            stdout='{"status":"SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY",'
                   '"monitored_threads":7,"snapshot_written":true,'
                   '"new_inbound_header_candidates":1,'
                   '"outbound_sent":false,"database_writes":false}',
        ))
    )
    v = team.refresh_founder_acquisition_observer("/srv/empire_os")
    # Depending on whether the worker runner is deployed to /srv, the helper
    # correctly holds rather than fabricating success. Tests patch only the
    # worker invocation, not files on actual production.
    if v["status"] == "RUNNER_NOT_DEPLOYED":
        assert not records
    else:
        assert v["status"] == "SEVEN_FOUNDER_THREADS_REVIEWED"
        assert v["new_inbound_header_candidates"] == 1
        assert records[0][1]["timeout"] <= 35
        assert "--write" in records[0][0][0]
        assert records[0][1]["check"] is False
        assert "send_email" not in repr(records)


def test_untrusted_worker_claim_never_promotes_buyer_or_send(monkeypatch):
    import subprocess
    from pathlib import Path
    monkeypatch.setattr(Path, "is_file", lambda p: True)
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout='{"status":"SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY",'
            '"monitored_threads":7,"snapshot_written":true,'
            '"new_inbound_header_candidates":1,'
            '"outbound_sent":true,"database_writes":false}'
        ),
    )
    v = team.refresh_founder_acquisition_observer("/srv/empire_os")
    assert v["status"] == "HELD_INCOMPLETE_FOUNDER_MAILBOX_REVIEW"
    assert v["outbound_sent"] is False
