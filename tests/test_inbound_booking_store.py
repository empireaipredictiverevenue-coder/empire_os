"""Persistent offline workflow isolation, replay and read-only tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_booking_workflow import InboundWorkflowEvent, WorkflowPolicy
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
SECRET = "internal-only-workflow-test-key-32-bytes"
CONTACT = pseudonymise_inbound_contact(
    "+442071234567", tenant_id="tenant-a", signing_key=SECRET,
)


def event(kind="callback_requested", *, tenant="tenant-a", event_id="e1",
          call_id="c1", synthetic=False, verified=True, minute=0):
    return InboundWorkflowEvent(
        tenant_id=tenant, event_id=event_id, call_id=call_id,
        contact_key=CONTACT, kind=kind,
        occurred_at=(NOW + timedelta(minutes=minute)).isoformat(),
        origin="operator_review",
        evidence_ref=f"operator-proof:{event_id}",
        synthetic=synthetic, verified=verified,
    )


def test_persisted_events_replay_without_duplicate(tmp_path):
    path = tmp_path / "workflow.sqlite"
    original = event()
    with OfflineBookingWorkflowStore(path) as store:
        assert store.append_offline(original)
        assert store.append_offline(original) is False
    with OfflineBookingWorkflowStore(path, read_only=True) as store:
        assert store.events_for_tenant("tenant-a") == (original,)
        assert store.events_for_tenant("tenant-b") == ()
        assert store.summary(WorkflowPolicy("tenant-a"), as_of=NOW)["call_workflows_total"] == 1
        with pytest.raises(ValueError, match="read_only"):
            store.append_offline(event(event_id="e2"))


def test_conflicting_id_refused_and_does_not_overwrite(tmp_path):
    with OfflineBookingWorkflowStore(tmp_path / "workflow.db") as store:
        first = event()
        store.append_offline(first)
        with pytest.raises(ValueError, match="conflicting"):
            store.append_offline(replace(first, call_id="c2"))
        assert store.events_for_tenant("tenant-a") == (first,)


def test_distinct_tenants_cannot_view_each_other(tmp_path):
    path = tmp_path / "workflow.db"
    with OfflineBookingWorkflowStore(path) as store:
        store.append_offline(event(event_id="shared", tenant="tenant-a", call_id="alpha"))
        store.append_offline(event(event_id="shared", tenant="tenant-b", call_id="beta"))
    with OfflineBookingWorkflowStore(path, read_only=True) as store:
        assert {e.call_id for e in store.events_for_tenant("tenant-a")} == {"alpha"}
        assert {e.call_id for e in store.events_for_tenant("tenant-b")} == {"beta"}


def test_missing_readonly_path_must_not_create_database(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="existing_workflow_database"):
        OfflineBookingWorkflowStore(missing, read_only=True)
    assert not missing.exists()


def test_integrity_check_rejects_tampered_event_bytes(tmp_path):
    path = tmp_path / "workflow.db"
    with OfflineBookingWorkflowStore(path) as store:
        store.append_offline(event())
        store.db.execute(
            "UPDATE inbound_workflow_evidence SET payload_json = '{}' WHERE event_id='e1'"
        )
        store.db.commit()
        with pytest.raises(ValueError, match="integrity_failure"):
            store.events_for_tenant("tenant-a")
