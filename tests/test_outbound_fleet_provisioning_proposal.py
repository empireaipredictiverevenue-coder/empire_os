from empire_os.outbound_fleet_provisioning_proposal import (
    build_fleet_provisioning_proposal,
)


def certificate(
    *,
    status="HOLD",
    required_domains=3,
    required_mailboxes=6,
    eligible_domains=1,
    eligible_mailboxes=2,
    capacity_gap=40,
):
    return {
        "status": status,
        "certificate_fingerprint": "a" * 64,
        "capacity": {
            "requirement": {
                "domains_needed": required_domains,
                "mailboxes_needed": required_mailboxes,
            },
            "plan": {
                "eligible_domains": [
                    f"d{i}.example" for i in range(eligible_domains)
                ],
                "eligible_mailbox_count": eligible_mailboxes,
                "capacity_gap": capacity_gap,
            },
        },
    }


def action(result, name):
    return next(
        row for row in result["actions"]
        if row["action"] == name
    )


def test_proposal_reports_missing_domain_and_mailbox_capacity():
    result = build_fleet_provisioning_proposal(
        certificate(),
        current_transport_keys=["t1"],
        current_ip_pool_keys=["p1"],
        verified_seed_families=["GOOGLE"],
    )
    domains = action(result, "PROPOSE_OUTREACH_DOMAINS")
    mailboxes = action(result, "PROPOSE_MAILBOX_CAPACITY")
    assert domains["count"] == 2
    assert mailboxes["minimum_new_mailboxes"] == 4
    assert mailboxes["unserved_daily_capacity"] == 40
    assert result["provisioning_authorized"] is False
    assert result["dns_mutation_authorized"] is False
    assert result["send_authorized"] is False


def test_proposal_requires_transport_and_ip_diversity_when_thin():
    result = build_fleet_provisioning_proposal(
        certificate(),
        current_transport_keys=["t1"],
        current_ip_pool_keys=["p1"],
        verified_seed_families=["GOOGLE", "MICROSOFT"],
        minimum_transport_count=2,
        minimum_ip_pool_count=2,
    )
    transport = action(result, "BENCHMARK_ADDITIONAL_TRANSPORT")
    ip_pool = action(result, "REDUCE_IP_POOL_CONCENTRATION")
    assert transport["minimum_additional_transports"] == 1
    assert ip_pool["minimum_additional_ip_pools"] == 1
    assert "no_automatic_failover" in transport["constraints"]
    assert "no_ip_churn" in ip_pool["constraints"]


def test_proposal_identifies_missing_seed_families():
    result = build_fleet_provisioning_proposal(
        certificate(),
        current_transport_keys=["t1", "t2"],
        current_ip_pool_keys=["p1", "p2"],
        verified_seed_families=["GOOGLE", "MICROSOFT"],
    )
    seeds = action(result, "ADD_OWNED_SEED_COVERAGE")
    assert seeds["mx_families"] == ["APPLE", "YAHOO"]
    assert "no_synthetic_engagement" in seeds["constraints"]


def test_no_gap_produces_no_provisioning_actions():
    result = build_fleet_provisioning_proposal(
        certificate(
            status="READY",
            required_domains=2,
            required_mailboxes=2,
            eligible_domains=2,
            eligible_mailboxes=2,
            capacity_gap=0,
        ),
        current_transport_keys=["t1", "t2"],
        current_ip_pool_keys=["p1", "p2"],
        verified_seed_families=[
            "GOOGLE",
            "MICROSOFT",
            "YAHOO",
            "APPLE",
        ],
    )
    assert result["posture"] == "NO_PROVISIONING_GAP"
    assert result["actions"] == []


def test_primary_safety_constraints_are_embedded_in_domain_proposal():
    result = build_fleet_provisioning_proposal(
        certificate(),
        current_transport_keys=["t1", "t2"],
        current_ip_pool_keys=["p1", "p2"],
        verified_seed_families=[
            "GOOGLE",
            "MICROSOFT",
            "YAHOO",
            "APPLE",
        ],
    )
    domains = action(result, "PROPOSE_OUTREACH_DOMAINS")
    assert "empire_owned" in domains["constraints"]
    assert "brand_safe" in domains["constraints"]
    assert "not_primary_brand" in domains["constraints"]
    assert "non_deceptive" in domains["constraints"]
    assert domains["approval_required"] is True
