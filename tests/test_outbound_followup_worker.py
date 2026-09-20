from datetime import datetime, timezone

from empire_os.outbound_followup_worker import (
    POSTAL_ADDRESS,
    build_followup_copy,
    run_followup_worker,
    within_send_window,
)


MONDAY = datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc)
SUNDAY = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def row(step=1):
    return {
        "root_intent_id": "00000000-0000-0000-0000-000000000001",
        "root_subject": "Clay — roofing opportunities in Wichita",
        "followup_step": step,
        "candidate_evidence": {
            "business_name": "Kihle Roofing",
            "niche": "roofing",
            "metro": "Wichita",
        },
    }


def test_copy_preserves_compliance_and_is_step_specific():
    subject, first = build_followup_copy(row(1))
    _, final = build_followup_copy(row(2))
    assert subject.startswith("Re:")
    assert "Kihle Roofing" in first
    assert "Worth a quick look?" in first
    assert "Last note from me" in final
    assert POSTAL_ADDRESS in first
    assert "opt out" in first.lower()
    assert POSTAL_ADDRESS in final
    assert "opt out" in final.lower()


def test_copy_does_not_infer_a_person_name():
    _, body = build_followup_copy(row(1))
    assert body.startswith("Hi,")
    assert "Hi Clay" not in body


def test_send_window_is_weekday_and_hour_bounded():
    assert within_send_window(MONDAY) is True
    assert within_send_window(SUNDAY) is False
    assert (
        within_send_window(
            datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
        )
        is False
    )


def test_worker_proposes_due_followups_only():
    calls = []

    def request(method, path, payload=None, **_kwargs):
        calls.append((method, path, payload))
        if path.endswith("list_due_outbound_followups"):
            return [row(1), row(2)]
        if path.endswith("propose_outbound_followup"):
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000099",
            }
        raise AssertionError(path)

    result = run_followup_worker(request, now=MONDAY)
    assert result.due_seen == 2
    assert result.proposed == 2
    assert result.errors == ()
    proposals = [
        payload
        for _method, path, payload in calls
        if path.endswith("propose_outbound_followup")
    ]
    assert proposals[0]["p_step"] == 1
    assert proposals[1]["p_step"] == 2
    assert proposals[0]["p_idempotency_key"].endswith(":step:1:v1")
    assert proposals[1]["p_idempotency_key"].endswith(":step:2:v1")


def test_worker_defers_without_touching_database_outside_window():
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    result = run_followup_worker(request, now=SUNDAY)
    assert result.deferred_outside_window is True
    assert result.due_seen == 0
    assert calls == []
