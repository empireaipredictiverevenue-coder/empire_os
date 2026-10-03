from empire_os.outbound_fleet_capacity_certificate import (
    build_fleet_capacity_certificate,
)


def domain(name):
    return {
        "domain": name,
        "empire_owned": True,
        "brand_safe": True,
        "sovereign": True,
        "health": "GREEN",
        "purpose": "prospecting",
        "primary_brand": False,
    }


def mailbox(key, domain_name, capacity, transport):
    return {
        "mailbox_key": key,
        "domain": domain_name,
        "health": "GREEN",
        "enabled": True,
        "remaining_capacity": capacity,
        "reputation_credit": 50,
        "transport_key": transport,
        "ip_pool_key": f"ip:{transport}",
    }


def test_ready_certificate_when_capacity_and_estate_are_healthy():
    result = build_fleet_capacity_certificate(
        approved_daily_volume=20,
        per_mailbox_cap=10,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example"), domain("b.example")],
        mailboxes=[
            mailbox("m1", "a.example", 10, "t1"),
            mailbox("m2", "b.example", 10, "t2"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        max_domain_share=0.50,
        minimum_domains=2,
    )
    assert result["status"] == "READY"
    assert result["plan"]["allocated"] == 20
    assert result["plan"]["capacity_gap"] == 0
    assert result["certificate_fingerprint"]
    assert result["send_authorized"] is False


def test_certificate_holds_when_safe_capacity_is_insufficient():
    result = build_fleet_capacity_certificate(
        approved_daily_volume=20,
        per_mailbox_cap=10,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example")],
        mailboxes=[mailbox("m1", "a.example", 20, "t1")],
        estate_reconciliation={"status": "CONVERGED"},
        max_domain_share=0.50,
        minimum_domains=2,
    )
    assert result["status"] == "HOLD"
    assert "safe_sender_capacity_gap" in result["blockers"]
    assert result["plan"]["capacity_gap"] == 10


def test_certificate_holds_on_estate_integrity_failure_even_with_capacity():
    result = build_fleet_capacity_certificate(
        approved_daily_volume=10,
        per_mailbox_cap=10,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example")],
        mailboxes=[mailbox("m1", "a.example", 10, "t1")],
        estate_reconciliation={"status": "HOLD"},
        max_domain_share=1.0,
        minimum_domains=1,
    )
    assert result["status"] == "HOLD"
    assert "sender_estate_not_converged" in result["blockers"]


def test_concentration_warns_without_expanding_capacity():
    result = build_fleet_capacity_certificate(
        approved_daily_volume=15,
        per_mailbox_cap=5,
        max_mailboxes_per_domain=1,
        domains=[
            domain("a.example"),
            domain("b.example"),
            domain("c.example"),
        ],
        mailboxes=[
            mailbox("m1", "a.example", 5, "t1"),
            mailbox("m2", "b.example", 5, "t1"),
            mailbox("m3", "c.example", 5, "t1"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        max_domain_share=1 / 3,
        minimum_domains=3,
    )
    assert result["status"] == "LIMITED"
    assert "sender_infrastructure_concentration_high" in result["warnings"]
    assert result["plan"]["allocated"] == 15
    assert result["provisioning_authorized"] is False


def test_certificate_is_deterministic_for_same_inputs():
    kwargs = dict(
        approved_daily_volume=10,
        per_mailbox_cap=5,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example"), domain("b.example")],
        mailboxes=[
            mailbox("m1", "a.example", 5, "t1"),
            mailbox("m2", "b.example", 5, "t2"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        max_domain_share=0.50,
        minimum_domains=2,
    )
    one = build_fleet_capacity_certificate(**kwargs)
    two = build_fleet_capacity_certificate(**kwargs)
    assert one["certificate_fingerprint"] == two["certificate_fingerprint"]
