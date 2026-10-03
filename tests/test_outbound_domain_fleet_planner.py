import pytest

from empire_os.outbound_domain_fleet_planner import (
    estimate_fleet_requirement,
    plan_existing_fleet_capacity,
)


def domain(name, **overrides):
    row = {
        "domain": name,
        "empire_owned": True,
        "brand_safe": True,
        "sovereign": True,
        "health": "GREEN",
        "purpose": "prospecting",
        "primary_brand": False,
    }
    row.update(overrides)
    return row


def mailbox(key, domain_name, capacity, **overrides):
    row = {
        "mailbox_key": key,
        "domain": domain_name,
        "health": "GREEN",
        "enabled": True,
        "remaining_capacity": capacity,
        "reputation_credit": 50,
        "transport_key": "transport:a",
    }
    row.update(overrides)
    return row


def test_estimate_fleet_requirement_respects_mailbox_and_domain_caps():
    result = estimate_fleet_requirement(
        approved_daily_volume=80,
        per_mailbox_cap=20,
        max_mailboxes_per_domain=2,
        minimum_domains=2,
    )
    assert result["mailboxes_needed"] == 4
    assert result["domains_needed"] == 2
    assert result["provisioning_authorized"] is False
    assert result["send_authorized"] is False


def test_primary_brand_domain_is_excluded_from_prospecting_capacity():
    result = plan_existing_fleet_capacity(
        [
            domain("outbound-a.example"),
            domain(
                "empire-ai.co.uk",
                primary_brand=True,
            ),
        ],
        [
            mailbox("m1", "outbound-a.example", 10),
            mailbox("m2", "empire-ai.co.uk", 10),
        ],
        approved_daily_volume=10,
        max_domain_share=1.0,
    )
    assert result["posture"] == "PLANNED"
    assert result["allocated"] == 10
    assert result["allocations"][0]["domain"] == "outbound-a.example"
    assert any(
        row["mailbox_key"] == "m2"
        and "domain_not_eligible" in row["reasons"]
        for row in result["rejected_mailboxes"]
    )


def test_domain_share_limit_forces_distribution():
    result = plan_existing_fleet_capacity(
        [
            domain("a.example"),
            domain("b.example"),
        ],
        [
            mailbox("a1", "a.example", 20, reputation_credit=90),
            mailbox("b1", "b.example", 20, reputation_credit=40),
        ],
        approved_daily_volume=20,
        max_domain_share=0.50,
    )
    assert result["posture"] == "PLANNED"
    assert result["domain_usage"] == {
        "a.example": 10,
        "b.example": 10,
    }


def test_capacity_gap_is_reported_not_bypassed():
    result = plan_existing_fleet_capacity(
        [domain("a.example")],
        [mailbox("a1", "a.example", 20)],
        approved_daily_volume=20,
        max_domain_share=0.50,
    )
    assert result["posture"] == "CAPACITY_GAP"
    assert result["allocated"] == 10
    assert result["capacity_gap"] == 10
    assert result["principle"] == (
        "capacity_gap_is_reported_not_bypassed_by_rotation"
    )


def test_zero_target_is_noop():
    result = plan_existing_fleet_capacity(
        [domain("a.example")],
        [mailbox("a1", "a.example", 20)],
        approved_daily_volume=0,
    )
    assert result["posture"] == "NOOP"
    assert result["allocated"] == 0
    assert result["capacity_gap"] == 0


def test_invalid_domain_share_is_rejected():
    with pytest.raises(ValueError, match="max_domain_share"):
        plan_existing_fleet_capacity(
            [domain("a.example")],
            [mailbox("a1", "a.example", 20)],
            approved_daily_volume=10,
            max_domain_share=0,
        )


def test_unsafe_or_unsovereign_domain_is_excluded():
    result = plan_existing_fleet_capacity(
        [
            domain("unsafe.example", brand_safe=False),
            domain("not-owned.example", empire_owned=False),
            domain("not-sovereign.example", sovereign=False),
        ],
        [
            mailbox("m1", "unsafe.example", 10),
            mailbox("m2", "not-owned.example", 10),
            mailbox("m3", "not-sovereign.example", 10),
        ],
        approved_daily_volume=10,
        max_domain_share=1.0,
    )
    assert result["posture"] == "CAPACITY_GAP"
    assert result["allocated"] == 0
    assert result["capacity_gap"] == 10
    assert result["eligible_domains"] == []
