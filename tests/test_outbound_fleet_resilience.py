from empire_os.outbound_fleet_resilience import evaluate_fleet_resilience


def sender(key, domain, transport, ip_pool, capacity=10):
    return {
        "mailbox_key": key,
        "domain": domain,
        "transport_key": transport,
        "ip_pool_key": ip_pool,
        "remaining_capacity": capacity,
        "health": "GREEN",
        "enabled": True,
    }


def benchmark():
    return {
        "results": [
            {"transport": "t1", "inbox_rate": 1.0},
            {"transport": "t2", "inbox_rate": 0.9},
        ]
    }


def test_diversified_fleet_has_strong_n_minus_one_survival():
    result = evaluate_fleet_resilience(
        [
            sender("m1", "a.example", "t1", "p1"),
            sender("m2", "b.example", "t2", "p2"),
            sender("m3", "c.example", "t3", "p3"),
            sender("m4", "d.example", "t4", "p4"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT", "YAHOO"],
        failover_benchmark=benchmark(),
    )
    assert result["posture"] == "RESILIENT"
    assert result["transport"]["worst_case_survival_rate"] == 0.75
    assert result["domain"]["worst_case_survival_rate"] == 0.75
    assert result["ip_pool"]["worst_case_survival_rate"] == 0.75
    assert result["score"] == 100.0
    assert result["send_authorized"] is False


def test_single_transport_dependency_is_flagged():
    result = evaluate_fleet_resilience(
        [
            sender("m1", "a.example", "t1", "p1"),
            sender("m2", "b.example", "t1", "p2"),
            sender("m3", "c.example", "t1", "p3"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=benchmark(),
    )
    assert result["transport"]["worst_case_survival_rate"] == 0.0
    assert "single_transport_blast_radius" in result["warnings"]
    assert result["posture"] in {"LIMITED", "FRAGILE"}


def test_single_high_capacity_domain_exposes_blast_radius():
    result = evaluate_fleet_resilience(
        [
            sender("m1", "a.example", "t1", "p1", capacity=30),
            sender("m2", "b.example", "t2", "p2", capacity=5),
            sender("m3", "c.example", "t3", "p3", capacity=5),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=benchmark(),
    )
    assert result["domain"]["worst_case_survival_rate"] == 0.25
    assert "single_domain_blast_radius" in result["warnings"]


def test_estate_integrity_hold_forces_resilience_hold():
    result = evaluate_fleet_resilience(
        [sender("m1", "a.example", "t1", "p1")],
        estate_reconciliation={"status": "HOLD"},
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        failover_benchmark=benchmark(),
    )
    assert result["posture"] == "HOLD"
    assert "sender_estate_integrity_hold" in result["blockers"]


def test_unmeasured_failover_and_thin_seed_coverage_are_visible():
    result = evaluate_fleet_resilience(
        [
            sender("m1", "a.example", "t1", "p1"),
            sender("m2", "b.example", "t2", "p2"),
        ],
        estate_reconciliation={"status": "CONVERGED"},
        verified_seed_families=["GOOGLE"],
    )
    assert result["failover_evidence"] == "UNMEASURED"
    assert "seed_provider_coverage_thin" in result["warnings"]
    assert "failover_transport_unmeasured" in result["warnings"]


def test_no_eligible_capacity_is_hold():
    result = evaluate_fleet_resilience(
        [{
            "mailbox_key": "m1",
            "domain": "a.example",
            "transport_key": "t1",
            "ip_pool_key": "p1",
            "remaining_capacity": 0,
            "health": "HOLD",
            "enabled": False,
        }],
        estate_reconciliation={"status": "CONVERGED"},
    )
    assert result["posture"] == "HOLD"
    assert "no_eligible_sender_capacity" in result["blockers"]
