import json
from datetime import datetime, timezone

from empire_os.signal_resolver import (
    candidate_from_signal,
    run_signal_resolution,
)


def permit_signal():
    return {
        "signal_id": "sig-1",
        "status": "unresolved",
        "created_at": "2026-09-21T10:00:00+00:00",
        "next_resolution_at": "2026-09-21T10:00:00+00:00",
        "source": "permits_nyc",
        "name": "Example Owner (Manhattan)",
        "niche": "general_contractor",
        "metro": "NYC",
        "state": "NY",
        "url": "https://example.gov/permit/123",
        "raw": {
            "job__": "123",
            "permittee_s_business_name": "Example Contracting LLC",
            "permittee_s_first_name": "Alex",
            "permittee_s_last_name": "Smith",
            "permittee_s_phone__": "2125550101",
            "permittee_s_license__": "GC123",
            "permittee_s_license_type": "GC",
            "house__": "10",
            "street_name": "MAIN STREET",
        },
    }


def test_permit_signal_builds_strong_identity_candidate():
    candidate, reason = candidate_from_signal(permit_signal())
    assert reason == "permittee_identity_complete"
    assert candidate is not None
    assert candidate.name == "Example Contracting LLC"
    assert candidate.phone == "2125550101"
    assert candidate.source == "permits_nyc_resolved"
    assert candidate.country_code == "US"
    assert candidate.timezone == "America/New_York"
    assert candidate.raw["permittee_license"] == "GC123"


def test_court_signal_stays_unresolved_without_external_identity():
    candidate, reason = candidate_from_signal({
        "source": "courtlistener",
        "raw": {"party": ["Example LLC"]},
    })
    assert candidate is None
    assert reason == "court_party_requires_external_identity_resolution"


def test_resolution_materializes_permit_and_marks_signal_resolved(tmp_path):
    inbox = tmp_path / "signal_inbox.json"
    lock = tmp_path / "signal_inbox.lock"
    inbox.write_text(json.dumps({"sig-1": permit_signal()}))

    def reader(_path, _params):
        return []

    def writer(payload):
        assert payload["prospect"]["business_name"] == "Example Contracting LLC"
        return {
            "decision": "created",
            "prospect": {"id": "prospect-1"},
        }

    result = run_signal_resolution(
        5,
        inbox=inbox,
        lock=lock,
        reader=reader,
        writer=writer,
        now=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
    )
    saved = json.loads(inbox.read_text())["sig-1"]
    assert result["resolved"] == 1
    assert result["failed"] == 0
    assert saved["status"] == "resolved"
    assert saved["prospect_id"] == "prospect-1"
    assert saved["resolution_reason"] == "canonical_prospect_created"


def test_ambiguous_signal_never_writes_canonical_prospect(tmp_path):
    inbox = tmp_path / "signal_inbox.json"
    lock = tmp_path / "signal_inbox.lock"
    inbox.write_text(json.dumps({"sig-1": permit_signal()}))

    def reader(_path, _params):
        return [
            {
                "id": "one",
                "business_name": "Example Contracting LLC",
                "phone": "2125550101",
                "metro": "NYC",
            },
            {
                "id": "two",
                "business_name": "Example Contracting LLC",
                "phone": "2125550101",
                "metro": "NYC",
            },
        ]

    def writer(_payload):
        raise AssertionError("ambiguous identity must not write")

    result = run_signal_resolution(
        5,
        inbox=inbox,
        lock=lock,
        reader=reader,
        writer=writer,
        now=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
    )
    saved = json.loads(inbox.read_text())["sig-1"]
    assert result["needs_review"] == 1
    assert saved["status"] == "needs_review"
