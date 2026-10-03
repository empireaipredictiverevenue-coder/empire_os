from datetime import datetime, timezone

from empire_os.outbound_account_saturation import evaluate_account_saturation


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def candidate():
    return {
        "company_key": "company:a",
        "parent_company_key": "parent:p",
        "corridor_key": "uk:roofing:northwest",
    }


def test_existing_conversation_blocks_new_cold_outreach():
    result = evaluate_account_saturation(
        candidate(),
        [{
            "company_key": "company:a",
            "event_kind": "reply_received",
            "occurred_at": "2026-10-02T10:00:00+00:00",
        }],
        now=NOW,
    )
    assert result["decision"] == "HOLD_NEW_OUTREACH"
    assert result["reason"] == "existing_company_conversation_takes_precedence"


def test_company_rolling_cap_blocks_new_outreach():
    history = [
        {
            "company_key": "company:a",
            "event_kind": "sent",
            "occurred_at": f"2026-09-{20 + i:02d}T10:00:00+00:00",
        }
        for i in range(4)
    ]
    result = evaluate_account_saturation(candidate(), history, now=NOW)
    assert result["decision"] == "HOLD_NEW_OUTREACH"
    assert result["reason"] == "company_saturation_limit_reached"


def test_parent_group_cap_prevents_agent_pile_on_across_subsidiaries():
    history = [
        {
            "company_key": f"company:{i}",
            "parent_company_key": "parent:p",
            "event_kind": "outbound_touch",
            "occurred_at": "2026-10-01T10:00:00+00:00",
        }
        for i in range(8)
    ]
    result = evaluate_account_saturation(candidate(), history, now=NOW)
    assert result["decision"] == "HOLD_NEW_OUTREACH"
    assert result["reason"] == "parent_group_saturation_limit_reached"


def test_corridor_cap_throttles_without_global_hold():
    history = [
        {
            "company_key": f"company:{i}",
            "parent_company_key": f"parent:{i}",
            "corridor_key": "uk:roofing:northwest",
            "event_kind": "sent",
            "occurred_at": "2026-10-02T10:00:00+00:00",
        }
        for i in range(20)
    ]
    result = evaluate_account_saturation(candidate(), history, now=NOW)
    assert result["decision"] == "THROTTLE_CORRIDOR"
    assert result["reason"] == "corridor_saturation_limit_reached"


def test_old_contacts_fall_outside_rolling_window():
    history = [
        {
            "company_key": "company:a",
            "parent_company_key": "parent:p",
            "corridor_key": "uk:roofing:northwest",
            "event_kind": "sent",
            "occurred_at": "2026-01-01T10:00:00+00:00",
        }
        for _ in range(20)
    ]
    result = evaluate_account_saturation(candidate(), history, now=NOW)
    assert result["decision"] == "READY"


def test_missing_company_identity_escalates():
    result = evaluate_account_saturation({}, [], now=NOW)
    assert result["decision"] == "ESCALATE"
    assert result["reason"] == "company_identity_missing"
