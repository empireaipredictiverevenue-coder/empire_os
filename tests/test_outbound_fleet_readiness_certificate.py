from empire_os.outbound_fleet_readiness_certificate import (
    build_fleet_readiness_certificate,
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


def mailbox(key, domain_name, transport, ip_pool, capacity=10):
    return {
        "mailbox_key": key,
        "domain": domain_name,
        "health": "GREEN",
        "enabled": True,
        "remaining_capacity": capacity,
        "reputation_credit": 50,
        "transport_key": transport,
        "ip_pool_key": ip_pool,
    }


def failover():
    return {
        "results": [
            {"transport": "t1", "inbox_rate": 0.98},
            {"transport": "t2", "inbox_rate": 0.96},
        ]
    }


def test_ready_certificate_requires_capacity_and_resilience():
    result = build_fleet_readiness_certificate(
        approved_daily_volume=20,
        per_mailbox_cap=10,
        max_mailboxes_per_domain=1,
        domains=[
            domain("a.example"),
            domain("b.example"),
            domain("c.example"),
            domain("d.example"),
        ],
        mailboxes=[
            mailbox("m1", "a.example", "t1", "p1", 5),
            mailbox("m2", "b.example", "t2", "p2", 5),
            mailbox("m3", "c.example", "t3", "p3", 5),
            mailbox("m4", "d.example", "t4", "p4", 5),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT", "YAHOO"],
        failover_benchmark=failover(),
        max_domain_share=0.25,
        minimum_domains=4,
    )
    assert result["status"] == "READY"
    assert result["capacity"]["status"] == "READY"
    assert result["resilience"]["posture"] == "RESILIENT"
    assert result["send_authorized"] is False


def test_capacity_gap_forces_hold_even_if_resilience_inputs_exist():
    result = build_fleet_readiness_certificate(
        approved_daily_volume=20,
        per_mailbox_cap=10,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example")],
        mailboxes=[mailbox("m1", "a.example", "t1", "p1", 20)],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=failover(),
        max_domain_share=0.50,
        minimum_domains=2,
    )
    assert result["status"] == "HOLD"
    assert "safe_sender_capacity_gap" in result["blockers"]


def test_fragile_fleet_is_limited_even_with_enough_capacity():
    result = build_fleet_readiness_certificate(
        approved_daily_volume=15,
        per_mailbox_cap=5,
        max_mailboxes_per_domain=1,
        domains=[
            domain("a.example"),
            domain("b.example"),
            domain("c.example"),
        ],
        mailboxes=[
            mailbox("m1", "a.example", "t1", "p1", 5),
            mailbox("m2", "b.example", "t1", "p1", 5),
            mailbox("m3", "c.example", "t1", "p1", 5),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=failover(),
        max_domain_share=1 / 3,
        minimum_domains=3,
    )
    assert result["capacity"]["status"] in {"READY", "LIMITED"}
    assert result["resilience"]["posture"] in {"LIMITED", "FRAGILE"}
    assert result["status"] == "LIMITED"


def test_estate_hold_propagates_to_readiness_hold():
    result = build_fleet_readiness_certificate(
        approved_daily_volume=5,
        per_mailbox_cap=5,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example")],
        mailboxes=[mailbox("m1", "a.example", "t1", "p1", 5)],
        estate_reconciliation={"status": "HOLD"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=failover(),
        max_domain_share=1.0,
        minimum_domains=1,
    )
    assert result["status"] == "HOLD"
    assert "sender_estate_not_converged" in result["blockers"]


def test_readiness_certificate_is_deterministic():
    kwargs = dict(
        approved_daily_volume=10,
        per_mailbox_cap=5,
        max_mailboxes_per_domain=1,
        domains=[domain("a.example"), domain("b.example")],
        mailboxes=[
            mailbox("m1", "a.example", "t1", "p1", 5),
            mailbox("m2", "b.example", "t2", "p2", 5),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=failover(),
        max_domain_share=0.50,
        minimum_domains=2,
    )
    one = build_fleet_readiness_certificate(**kwargs)
    two = build_fleet_readiness_certificate(**kwargs)
    assert one["certificate_fingerprint"] == two["certificate_fingerprint"]
