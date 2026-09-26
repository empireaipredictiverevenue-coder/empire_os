from datetime import datetime, timezone

from empire_os.outbound_followup_worker import (
    POSTAL_ADDRESS,
    build_followup_copy,
    followup_contact_eligibility,
    run_followup_worker,
)


MONDAY = datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc)
SUNDAY = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def row(step=1, metro="Wichita"):
    return {
        "root_intent_id": "00000000-0000-0000-0000-000000000001",
        "root_subject": "Clay — roofing opportunities in Wichita",
        "followup_step": step,
        "candidate_evidence": {
            "business_name": "Kihle Roofing",
            "niche": "roofing",
            "metro": metro,
        },
    }


def test_copy_preserves_compliance_and_is_step_specific():
    subject, first = build_followup_copy(row(1))
    _, final = build_followup_copy(row(2))
    assert subject.startswith("Re:")
    assert "Kihle Roofing" in first
    assert "one-page Wichita roofing brief" in first
    assert "send it" in first.lower()
    assert "Closing the loop" in final
    assert POSTAL_ADDRESS in first
    assert "opt out" in first.lower()
    assert POSTAL_ADDRESS in final
    assert "opt out" in final.lower()


def test_copy_does_not_infer_a_person_name():
    _, body = build_followup_copy(row(1))
    assert body.startswith("Hi,")
    assert "Hi Clay" not in body


def test_city_only_market_resolves_unique_local_timezone():
    result = followup_contact_eligibility(row(metro="Wichita"), now=MONDAY)
    assert result["locale"]["timezone"] == "America/Chicago"
    assert result["locale"]["outreach_language"] == "en-US"
    assert result["eligible"] is True
    assert result["timing"]["local_hour"] == 11


def test_recipient_local_weekend_blocks_even_when_utc_is_weekday():
    # 2026-09-21 00:30 UTC is Monday UTC but Sunday evening in Wichita.
    now = datetime(2026, 9, 21, 0, 30, tzinfo=timezone.utc)
    result = followup_contact_eligibility(row(), now=now)
    assert result["eligible"] is False
    assert result["reason"] == "recipient_local_weekend"


def test_non_english_followup_fails_closed_until_localized_copy_exists():
    german = row(metro="Berlin")
    result = followup_contact_eligibility(german, now=MONDAY)
    assert result["eligible"] is False
    assert result["reason"] == "localized_followup_copy_unavailable:de-DE"


def test_worker_proposes_only_rows_inside_recipient_local_window():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if path.endswith("list_due_outbound_followups"):
            return [
                row(1, "Wichita"),
                row(1, "Sydney, NSW"),
            ]
        if path.endswith("propose_outbound_followup"):
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000099",
            }
        raise AssertionError(path)

    result = run_followup_worker(request, now=MONDAY)
    assert result.due_seen == 2
    assert result.proposed == 1
    assert result.local_window_deferred == 1
    assert result.locale_blocked == 0
    assert result.errors == ()
    proposals = [
        payload
        for _method, path, payload in calls
        if path.endswith("propose_outbound_followup")
    ]
    assert len(proposals) == 1
    assert proposals[0]["p_idempotency_key"].endswith(":step:1:v2-local")


def test_worker_queries_due_projection_even_on_utc_weekend():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if path.endswith("list_due_outbound_followups"):
            return []
        raise AssertionError(path)

    result = run_followup_worker(request, now=SUNDAY)
    assert result.due_seen == 0
    assert result.proposed == 0
    assert len(calls) == 1
