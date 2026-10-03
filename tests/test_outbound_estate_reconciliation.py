from empire_os.outbound_estate_reconciliation import reconcile_sender_estate


def base_inventory():
    transports = [{
        "id": "t1",
        "transport_key": "transport:a",
        "state": "ACTIVE",
        "policy_compatible": True,
    }]
    domains = [{
        "id": "d1",
        "domain": "mail.example.com",
        "lifecycle_state": "ACTIVE",
    }]
    mailboxes = [{
        "id": "m1",
        "mailbox_key": "sender:1",
        "email_address": "sender@mail.example.com",
        "domain_id": "d1",
        "transport_id": "t1",
        "state": "ACTIVE",
        "reputation_credit": 50,
    }]
    pools = [{
        "id": "p1",
        "pool_key": "mailbox:primary",
        "pool_kind": "MAILBOX",
        "state": "ACTIVE",
    }]
    members = [{
        "pool_id": "p1",
        "member_type": "MAILBOX",
        "member_key": "sender:1",
        "active": True,
    }]
    capacity = [{
        "id": "c1",
        "mailbox_key": "sender:1",
        "domain": "mail.example.com",
        "transport_key": "transport:a",
        "event_type": "SET_LIMIT",
        "capacity_limit": 20,
        "units": 0,
        "recorded_at": "2026-10-03T08:00:00+00:00",
    }]
    seeds = [{
        "seed_key": "seed:gmail:1",
        "active": True,
        "ownership_verified": True,
    }]
    return transports, domains, mailboxes, pools, members, capacity, seeds


def test_healthy_sender_estate_converges():
    args = base_inventory()
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=args[4],
        capacity_events=args[5],
        seed_mailboxes=args[6],
    )
    assert result["status"] == "CONVERGED"
    assert result["sender_estate"]["eligible_count"] == 1
    assert result["sender_estate"]["eligible_senders"][0]["remaining_capacity"] == 20
    assert result["mutation_authorized"] is False
    assert result["send_authorized"] is False


def test_capacity_for_unknown_mailbox_is_hard_hold():
    args = base_inventory()
    capacity = list(args[5]) + [{
        "id": "c2",
        "mailbox_key": "sender:missing",
        "domain": "mail.example.com",
        "event_type": "SET_LIMIT",
        "capacity_limit": 10,
        "units": 0,
        "recorded_at": "2026-10-03T09:00:00+00:00",
    }]
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=args[4],
        capacity_events=capacity,
        seed_mailboxes=args[6],
    )
    assert result["status"] == "HOLD"
    assert "capacity_event_unknown_mailbox" in result["hard_holds"]


def test_capacity_identity_mismatch_is_hard_hold():
    args = base_inventory()
    capacity = [{
        **args[5][0],
        "domain": "wrong.example.com",
        "transport_key": "transport:wrong",
    }]
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=args[4],
        capacity_events=capacity,
        seed_mailboxes=args[6],
    )
    assert result["status"] == "HOLD"
    assert "capacity_event_domain_mismatch" in result["hard_holds"]
    assert "capacity_event_transport_mismatch" in result["hard_holds"]


def test_orphaned_pool_member_is_hard_hold():
    args = base_inventory()
    members = [{
        "pool_id": "p1",
        "member_type": "MAILBOX",
        "member_key": "sender:missing",
        "active": True,
    }]
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=members,
        capacity_events=args[5],
        seed_mailboxes=args[6],
    )
    assert result["status"] == "HOLD"
    assert "pool_member_orphaned_asset" in result["hard_holds"]


def test_active_pool_without_members_is_degraded():
    args = base_inventory()
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=[],
        capacity_events=args[5],
        seed_mailboxes=args[6],
    )
    assert result["status"] == "DEGRADED"
    assert "active_pool_has_no_members" in result["warnings"]


def test_no_verified_seed_mailbox_is_degraded():
    args = base_inventory()
    seeds = [{
        "seed_key": "seed:gmail:1",
        "active": True,
        "ownership_verified": False,
    }]
    result = reconcile_sender_estate(
        transports=args[0],
        domains=args[1],
        mailboxes=args[2],
        pools=args[3],
        pool_members=args[4],
        capacity_events=args[5],
        seed_mailboxes=seeds,
    )
    assert result["status"] == "DEGRADED"
    assert "no_active_verified_seed_mailboxes" in result["warnings"]
