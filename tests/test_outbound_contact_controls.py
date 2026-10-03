from datetime import datetime, timezone

from empire_os.outbound_contact_pressure import evaluate_contact_pressure
from empire_os.outbound_sender_affinity import resolve_sender_affinity
from empire_os.outbound_reputation_slo import evaluate_reputation_slo


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_person_cooldown_blocks_cross_agent_duplicate_contact():
    result = evaluate_contact_pressure(
        {"person_key": "person:a", "company_key": "company:x"},
        [{
            "person_key": "person:a",
            "company_key": "company:x",
            "occurred_at": "2026-10-01T10:00:00+00:00",
        }],
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "person_contact_cooldown_active"


def test_company_pressure_blocks_multiple_agents_same_day():
    history = [
        {
            "person_key": f"person:{n}",
            "company_key": "company:x",
            "occurred_at": "2026-10-03T09:00:00+00:00",
        }
        for n in range(2)
    ]
    result = evaluate_contact_pressure(
        {"person_key": "person:new", "company_key": "company:x"},
        history,
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert result["reason"] == "company_contact_pressure_limit"


def test_existing_thread_stays_with_healthy_sender():
    result = resolve_sender_affinity({
        "is_existing_thread": True,
        "prior_sender_id": "s1",
        "prior_sender_health": "GREEN",
        "proposed_sender_id": "s2",
    })
    assert result["decision"] == "HOLD"
    assert result["required_sender_id"] == "s1"


def test_reputation_slo_exhausts_on_excess_bounces():
    result = evaluate_reputation_slo({
        "sent": 100,
        "bounces": 3,
        "complaints": 0,
        "seed_tests": 10,
        "spam_placements": 0,
    })
    assert result["status"] == "EXHAUSTED"
    assert "bounce_budget" in result["exhausted"]
