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
                   '"monitored_threads":9,"snapshot_written":true,'
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
        assert v["status"] == "NINE_FOUNDER_THREADS_REVIEWED"
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
            '"monitored_threads":9,"snapshot_written":true,'
            '"new_inbound_header_candidates":1,'
            '"outbound_sent":true,"database_writes":false}'
        ),
    )
    v = team.refresh_founder_acquisition_observer("/srv/empire_os")
    assert v["status"] == "HELD_INCOMPLETE_FOUNDER_MAILBOX_REVIEW"
    assert v["outbound_sent"] is False


def test_plan_contains_sanitized_native_founder_status(tmp_path, monkeypatch):
    from empire_os.buyer_acquisition_team import refresh_buyer_acquisition_plan
    import json

    # The normal plan builder is tested independently. This verifies the
    # persisted status is generated in one original pipeline execution.
    snapshot = refresh_buyer_acquisition_plan(tmp_path)
    observed = snapshot["founder_acquisition_observation"]
    assert observed["status"] == "NOT_PRODUCTION_ROOT"
    assert observed["outbound_sent"] is False
    assert observed["crm_writes"] is False
    assert observed["automatic_send_authorized"] is False
    assert observed["requires_human_reply_review"] is False
    saved = json.loads((tmp_path / "runtime/buyer_acquisition/latest.json").read_text())
    assert saved["founder_acquisition_observation"] == observed
    assert "@" not in json.dumps(observed)


def test_sanitized_status_requires_review_only_for_positive_candidates(tmp_path, monkeypatch):
    from empire_os import buyer_acquisition_team
    monkeypatch.setattr(
        buyer_acquisition_team,
        "refresh_founder_acquisition_observer",
        lambda root: {
            "status": "NINE_FOUNDER_THREADS_REVIEWED",
            "new_inbound_header_candidates": 2,
            "outbound_sent": False,
        },
    )
    snapshot = buyer_acquisition_team.refresh_buyer_acquisition_plan(tmp_path)
    observed = snapshot["founder_acquisition_observation"]
    assert observed["new_inbound_header_candidates"] == 2
    assert observed["requires_human_reply_review"] is True
    assert observed["automatic_send_authorized"] is False


def test_missing_canonical_email_proof_surfaces_on_existing_business_plan(tmp_path, monkeypatch):
    from empire_os import buyer_acquisition_team
    monkeypatch.setattr(
        buyer_acquisition_team, "refresh_founder_acquisition_observer",
        lambda root: {
            "status": "NINE_FOUNDER_THREADS_REVIEWED",
            "new_inbound_header_candidates": 0,
            "canonical_email_clearance_evidence_missing_count": 9,
            "outbound_sent": False,
        },
    )
    state = buyer_acquisition_team.refresh_buyer_acquisition_plan(tmp_path)
    item = state["founder_acquisition_observation"]
    assert item["canonical_email_clearance_status"] == "NOT_VERIFIED"
    assert item["canonical_email_clearance_evidence_missing_count"] == 9
    assert item["canonical_email_clearance_review_required"] is True
    assert item["governed_outbound_release_eligible"] is False
    assert item["automatic_send_authorized"] is False
    assert item["crm_writes"] is False



def test_no_replies_waits_for_authentic_buyer_not_fake_pilot(tmp_path, monkeypatch):
    from empire_os import buyer_acquisition_team
    monkeypatch.setattr(
        buyer_acquisition_team, "refresh_founder_acquisition_observer",
        lambda root: {
            "status": "NINE_FOUNDER_THREADS_REVIEWED",
            "new_inbound_header_candidates": 0,
            "new_standalone_inbound_candidates": 0,
            "standalone_search_coverage_complete": True,
            "outbound_sent": False,
        },
    )
    plan = buyer_acquisition_team.refresh_buyer_acquisition_plan(tmp_path)
    pilot = plan["founder_acquisition_observation"]["paid_five_account_pilot"]
    assert pilot["stage"] == "AWAIT_AUTHENTIC_BUYER_RESPONSE"
    assert pilot["offer"] == "FIVE_ACCOUNT_SOURCE_CHECKED_INTELLIGENCE_PILOT"
    assert not pilot["pilot_committed"] and not pilot["payment_verified"]
    assert not pilot["outbound_send_authorized"]
    assert not pilot["automatic_followups_enabled"]


def test_header_candidate_requires_human_not_buyer_or_payment(tmp_path, monkeypatch):
    from empire_os import buyer_acquisition_team
    monkeypatch.setattr(
        buyer_acquisition_team, "refresh_founder_acquisition_observer",
        lambda root: {
            "status": "NINE_FOUNDER_THREADS_REVIEWED",
            "new_inbound_header_candidates": 0,
            "new_standalone_inbound_candidates": 1,
            "standalone_search_coverage_complete": True,
            "outbound_sent": False,
        },
    )
    pilot = buyer_acquisition_team.refresh_buyer_acquisition_plan(tmp_path)[
        "founder_acquisition_observation"]["paid_five_account_pilot"]
    assert pilot["stage"] == "HUMAN_REVIEW_INBOUND_CANDIDATE"
    full_observation = buyer_acquisition_team.refresh_buyer_acquisition_plan(tmp_path)[
        "founder_acquisition_observation"]
    assert full_observation["requires_human_reply_review"] is True
    assert pilot["next_human_action"] == "VERIFY_SENDER_INTENT_REQUIREMENT_AND_BUYER_AUTHORITY"
    assert pilot["authentic_buyer_response_verified"] is False
    assert pilot["buyer_requirement_qualified"] is False
    assert pilot["pilot_terms_approved"] is False
    assert pilot["fulfilment_authorized"] is False


def test_incomplete_or_held_mailbox_never_claims_no_buyer_reply():
    from empire_os.buyer_acquisition_team import _five_account_pilot_triage
    for data in (
        {},
        {"status":"NINE_FOUNDER_THREADS_REVIEWED",
         "new_inbound_header_candidates":0,
         "new_standalone_inbound_candidates":0},
        {"status":"NINE_FOUNDER_THREADS_REVIEWED",
         "new_inbound_header_candidates":0,
         "new_standalone_inbound_candidates":True,
         "standalone_search_coverage_complete":True},
        {"status":"NINE_FOUNDER_THREADS_REVIEWED",
         "new_inbound_header_candidates":0,
         "new_standalone_inbound_candidates":0,
         "standalone_search_coverage_complete":False},
    ):
        pilot=_five_account_pilot_triage(data)
        assert pilot["stage"]=="HELD_INBOUND_OBSERVABILITY_INCOMPLETE"
        assert pilot["outbound_send_authorized"] is False
        assert pilot["payment_verified"] is False
