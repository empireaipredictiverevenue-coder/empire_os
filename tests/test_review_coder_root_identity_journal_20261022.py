"""Fail closed on fabricated messages or journal provenance."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
import pytest

from scripts import review_coder_root_identity_journal_20261022 as audit

PID = 4064398


def example_event() -> dict:
    payload = {
        "actual_worker_pid": PID, "agent_id": "empire_coder",
        "canonical_task_claimed": False, "execution_authority": "none",
        "live_collaboration_activated": False,
        "persistent_signing_key_issued": False, "registered_agent": False,
        "root_helper_identity_preflight": True,
        "status": audit.POSITIVE, "unit": audit.UNIT,
    }
    ts = int(datetime(2026,10,22,17,32,15,tzinfo=timezone.utc).timestamp()*1_000_000)
    return {
        "MESSAGE": audit.PREFIX + json.dumps(payload, sort_keys=True),
        "_PID": str(PID), "_UID": "1000",
        "_SYSTEMD_UNIT": audit.UNIT,
        "_SYSTEMD_CGROUP": "/system.slice/" + audit.UNIT,
        "_SYSTEMD_INVOCATION_ID": "a"*32, "_TRANSPORT": "stdout",
        "__REALTIME_TIMESTAMP": str(ts),
    }


def test_realistic_kernel_verified_process_observation_is_historical_only():
    row = audit.verify_journal_event(example_event(), expected_uid=1000)
    assert row["status"] == "VERIFIED_HISTORICAL_CODER_ROOT_HELPER_PROCESS_PROVENANCE"
    assert row["kernel_journal_pid_uid_unit_cgroup_match"] is True
    assert row["historical_process_only"] is True
    assert row["registered_production_agents"] == 0
    assert row["persistent_signing_key_issued"] is False
    assert row["canonical_queue_modified_by_preflight"] is False
    assert row["trusted_message_sent"] is False


@pytest.mark.parametrize("field,new_value", [
    ("_PID","4064401"),("_UID","0"),
    ("_SYSTEMD_UNIT","empire-department-cycle.service"),
    ("_SYSTEMD_CGROUP","/system.slice/empire-department-cycle.service"),
    ("_SYSTEMD_CGROUP","/system.slice/empire-coder-worker.service-fake"),
    ("_SYSTEMD_INVOCATION_ID",""),
    ("_SYSTEMD_INVOCATION_ID","not_a_hex_identifier"),
    ("_TRANSPORT","syslog"),
    ("__REALTIME_TIMESTAMP","invalid"),
    ("__REALTIME_TIMESTAMP","0"),
])
def test_inconsistent_kernel_journal_metadata_is_refused(field,new_value):
    event=example_event()
    event[field]=new_value
    assert audit.verify_journal_event(event,expected_uid=1000) is None


@pytest.mark.parametrize("key,new_value", [
    ("actual_worker_pid",0),
    ("actual_worker_pid",4064399),
    ("agent_id","jev"),
    ("unit","empire-department-cycle.service"),
    ("status","SELF_ASSERTED"),
    ("root_helper_identity_preflight",False),
    ("canonical_task_claimed",True),
    ("live_collaboration_activated",True),
    ("persistent_signing_key_issued",True),
    ("registered_agent",True),
    ("execution_authority","send"),
])
def test_payload_tampering_or_exaggerated_authority_is_refused(key,new_value):
    event=example_event()
    body=json.loads(event["MESSAGE"][len(audit.PREFIX):])
    body[key]=new_value
    event["MESSAGE"]=audit.PREFIX+json.dumps(body)
    assert audit.verify_journal_event(event,expected_uid=1000) is None


def test_extra_field_and_fake_journal_message_not_promoted():
    event=example_event()
    body=json.loads(event["MESSAGE"][len(audit.PREFIX):])
    body["private_key"]="dummy"
    event["MESSAGE"]=audit.PREFIX+json.dumps(body)
    assert audit.verify_journal_event(event,expected_uid=1000) is None
    assert audit.verify_journal_event({"MESSAGE":example_event()["MESSAGE"]},
                                       expected_uid=1000) is None


def test_multiple_events_are_counted_and_no_registrations_ever_asserted():
    result=audit.review(events=[example_event(),example_event()],expected_uid=1000)
    assert result["verified_historical_process_observation_count"] == 2
    assert result["registered_production_agents"] == 0
    assert result["live_collaboration_activated"] is False


def test_empty_or_wrong_user_returns_hold():
    assert audit.review(events=[],expected_uid=1000)["status"] == (
        "NO_VERIFIED_CODER_ROOT_HELPER_ORIGIN_PROOF")
    assert audit.review(events=[example_event()],expected_uid=0)["status"] == (
        "NO_VERIFIED_CODER_ROOT_HELPER_ORIGIN_PROOF")


def test_cli_requires_read_only_authority_argument(monkeypatch,capsys):
    monkeypatch.setattr(audit.sys,"argv",["audit"])
    assert audit.main()==2
    assert "EXACT_READ_ONLY" in capsys.readouterr().out


def test_scoped_pinned_research_admission_not_assumed():
    from empire_os.agent_runtime_identity_evidence import MANAGED_WORKERS
    by_id={spec.agent_id: spec for spec in MANAGED_WORKERS}
    assert "empire_coder" in by_id
    assert "research" not in by_id
    assert "department_executive" in by_id
    assert by_id["department_executive"].department == "strategy"
    assert by_id["department_executive"].role == "executive_operations"
