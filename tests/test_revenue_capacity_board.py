from empire_os.revenue_capacity_board import (
    build_revenue_capacity_board,
)


RECURRING = {
    "local_search_grid": 7900,
    "content_protection": 9900,
    "geo_ai_visibility": 14900,
    "authority_intelligence": 14900,
    "search_growth_command": 29900,
    "serp_intelligence_api": 9900,
    "permit_intelligence": 49900,
    "property_intelligence": 79900,
}


def _catalog():
    products = []

    for code, amount in RECURRING.items():
        products.append({
            "product_code": code,
            "active": True,
            "binding_terms_ready": True,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
            "price_basis": {
                "state": "VERIFIED",
                "amount_cents": amount,
            },
        })

    for code in (
        "exchange_seat_starter",
        "exchange_seat_growth",
        "exchange_seat_pro",
        "exchange_seat_enterprise",
    ):
        products.append({
            "product_code": code,
            "active": True,
            "binding_terms_ready": False,
            "catalog_state": "UNKNOWN",
            "version_state": "PENDING",
        })

    return {
        "products": products,
    }


def _pricing():
    return {
        "products": [
            {
                "product_code": code,
                "billing_model": (
                    "usage_and_subscription"
                    if code
                    == "serp_intelligence_api"
                    else "monthly_subscription"
                ),
                "amount_cents": amount,
            }
            for code, amount
            in RECURRING.items()
        ],
    }


def _stage2():
    return {
        "campaign_ready_product_codes":
            list(RECURRING),
    }


def _exchange_plan():
    rows = (
        (
            "exchange_seat_starter",
            9900,
        ),
        (
            "exchange_seat_growth",
            24900,
        ),
        (
            "exchange_seat_pro",
            49900,
        ),
        (
            "exchange_seat_enterprise",
            99900,
        ),
    )

    return {
        "products": [
            {
                "product_code": code,
                "monthly_price_cents":
                    amount,
            }
            for code, amount in rows
        ],
        "base_usage_prices_cents": {
            "verified": 3900,
            "qualified": 5900,
            "high_intent": 9900,
            "exclusive": 14900,
            "booked_appointment_floor":
                19900,
        },
    }


def _pulse():
    return {
        "recognized_revenue_truth": {
            "recognized_revenue_cents":
                0,
            "realized_gp_cents":
                0,
        },
        "current_window": {
            "label": "current_24h",
            "verified_payments": 0,
            "fulfilments": 0,
        },
        "highest_priority_blocker":
            "qualification_v2",
        "snapshot_source":
            "canonical_supabase_postgres",
    }


def _queue():
    return {
        "highest_priority_blocker":
            "qualification_v2",
        "items": [
            {
                "company_name": "A",
                "current_commercial_state":
                    "READY",
                "product_code": None,
                "offer_known": False,
            },
            {
                "company_name": "B",
                "current_commercial_state":
                    "CONVERSATION",
                "product_code": None,
                "offer_known": False,
            },
        ],
    }


def _exchange():
    return {
        "buyer_seat_count": 1057,
        "corridor_count": 155,
        "inventory_count": 173,
        "allocation_candidate_count": 0,
        "actual_revenue": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def test_board_preserves_revenue_truth_and_unknown_mrr():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=_catalog(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
    )

    assert (
        board["schema_version"]
        == "empire.revenue_capacity_board.v1"
    )

    assert (
        board["actual"]
        ["recognized_revenue_cents"]
        == 0
    )

    assert (
        board["verified_mrr"]["amount_cents"]
        is None
    )

    assert (
        board["committed_mrr"]["amount_cents"]
        is None
    )

    assert (
        board["pipeline"]["monetary_value_cents"]
        is None
    )

    assert (
        board["pipeline"]["weighted_value_cents"]
        is None
    )

    assert (
        board["truth_guards"]
        ["pipeline_is_revenue"]
        is False
    )


def test_board_builds_stage2_recurring_capacity():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=_catalog(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
    )

    capacity = board[
        "sellable_capacity"
    ]

    assert (
        capacity[
            "stage2_ready_recurring_count"
        ]
        == 8
    )

    assert (
        capacity[
            "one_of_each_stack_mrr_cents"
        ]
        == 217200
    )

    assert (
        capacity[
            "one_of_each_stack_mrr_usd"
        ]
        == 2172.0
    )

    target_100k = board[
        "targets"
    ][0]

    assert (
        target_100k[
            "target_mrr_usd"
        ]
        == 100000.0
    )

    assert (
        target_100k[
            "full_sellable_recurring_stack_customer_equivalent"
        ]
        == 47
    )

    assert (
        target_100k[
            "verified_mrr_gap_cents"
        ]
        is None
    )


def test_exchange_records_never_become_customers_or_revenue():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=_catalog(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
    )

    runtime = board[
        "exchange_runtime"
    ]

    assert (
        runtime["buyer_seat_count"]
        == 1057
    )

    assert (
        runtime[
            "allocation_candidate_count"
        ]
        == 0
    )

    assert (
        runtime[
            "seat_records_are_customers"
        ]
        is False
    )

    assert (
        runtime["corridors_are_revenue"]
        is False
    )

    assert (
        board["locked_capacity"]
        ["product_count"]
        == 4
    )


def test_stale_supabase_label_is_flagged_not_trusted():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=_catalog(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
    )

    integrity = board[
        "source_integrity"
    ]

    assert (
        integrity[
            "legacy_supabase_label_detected"
        ]
        is True
    )

    assert (
        integrity[
            "backend_inferred_from_label"
        ]
        is False
    )

    assert (
        integrity[
            "source_label_state"
        ]
        == "STALE_LEGACY_LABEL_REQUIRES_RECONCILIATION"
    )


def _offer_book():
    return {
        "offer_ready": [
            {
                "company": "CooperBuild",
                "canonical_prospect_id": None,
                "person_name": "Adam Hicks",
                "person_verified": True,
                "conversation_state":
                    "UNKNOWN_REQUIRES_CANONICAL_RECONCILIATION",
                "commercial_role":
                    "RESEARCH_PROSPECT_NOT_VERIFIED_BUYER",
                "state": "OFFER_READY",
                "offer_package_ready": True,
                "buyer_demand_verified": False,
                "commercial_authority_verified": False,
                "live_send_ready": False,
                "execution_authority": "none",
                "expected_revenue_cents": None,
                "ready_product_codes": [
                    "permit_intelligence"
                ],
                "send_blockers": [
                    "verified_demand_unknown"
                ],
                "evidence_refs": [
                    "buyer_scout_candidate:test"
                ],
                "products": [
                    {
                        "product_code":
                            "permit_intelligence",
                        "billing_model":
                            "monthly_subscription",
                        "amount_cents":
                            49900,
                        "binding_terms_ready":
                            True,
                        "catalog_state":
                            "VERIFIED",
                        "version_state":
                            "VERIFIED",
                        "price_basis": {
                            "amount_cents":
                                49900,
                            "state":
                                "VERIFIED",
                        },
                    }
                ],
            },
            {
                "company":
                    "Private Investment Firm | Growth Capital | Kian Capital",
                "canonical_prospect_id":
                    None,
                "person_name":
                    "Rick Cravey",
                "person_verified":
                    True,
                "conversation_state":
                    "UNKNOWN_REQUIRES_CANONICAL_RECONCILIATION",
                "commercial_role":
                    "RESEARCH_PROSPECT_NOT_VERIFIED_BUYER",
                "state":
                    "OFFER_READY",
                "offer_package_ready":
                    True,
                "buyer_demand_verified":
                    False,
                "commercial_authority_verified":
                    False,
                "live_send_ready":
                    False,
                "execution_authority":
                    "none",
                "expected_revenue_cents":
                    None,
                "ready_product_codes": [
                    "private_capital_rollup"
                ],
                "send_blockers": [
                    "verified_demand_unknown"
                ],
                "evidence_refs": [
                    "buyer_scout_candidate:test2"
                ],
                "products": [
                    {
                        "product_code":
                            "private_capital_rollup",
                        "billing_model":
                            "monthly_subscription",
                        "amount_cents":
                            150000,
                        "binding_terms_ready":
                            True,
                        "catalog_state":
                            "VERIFIED",
                        "version_state":
                            "VERIFIED",
                        "price_basis": {
                            "amount_cents":
                                150000,
                            "state":
                                "VERIFIED",
                        },
                    }
                ],
            },
        ],
    }


def _enterprise_targets():
    return {
        "targets": [
            {
                "account_key":
                    "sila_services",
                "account_name":
                    "Sila Services",
                "account_type":
                    "multi_brand_home_services_platform",
                "fit_classification":
                    "INTERNAL_HYPOTHESIS",
                "evidence_classification":
                    "PUBLIC_OBSERVED_EVIDENCE",
                "target_product_codes": [
                    "predictive_revenue_intelligence_os",
                    "predictive_revenue_autonomous_os",
                ],
                "target_roles": [
                    "chief revenue officer"
                ],
                "observed_scale": [
                    "40+ brands"
                ],
                "observed_triggers": [
                    "multi-brand expansion"
                ],
                "binding_intent_verified":
                    False,
                "budget_verified":
                    False,
                "commercial_terms_verified":
                    False,
                "outreach_authorized":
                    False,
                "execution_authority":
                    "none",
            },
            {
                "account_key":
                    "redwood_services",
                "account_name":
                    "Redwood Services",
                "account_type":
                    "multi_brand_home_services_platform",
                "fit_classification":
                    "INTERNAL_HYPOTHESIS",
                "evidence_classification":
                    "PUBLIC_OBSERVED_EVIDENCE",
                "target_product_codes": [
                    "predictive_revenue_intelligence_os",
                    "predictive_revenue_private_strategic",
                ],
                "target_roles": [
                    "chief executive officer"
                ],
                "observed_scale": [
                    "national platform"
                ],
                "observed_triggers": [
                    "2026 acquisition"
                ],
                "binding_intent_verified":
                    False,
                "budget_verified":
                    False,
                "commercial_terms_verified":
                    False,
                "outreach_authorized":
                    False,
                "execution_authority":
                    "none",
            },
        ],
    }


def _catalog_with_locked_enterprise():
    d = _catalog()

    d["products"].extend([
        {
            "product_code":
                "private_capital_rollup",
            "active": True,
            "binding_terms_ready": True,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
            "price_basis": {
                "state": "VERIFIED",
                "amount_cents": 150000,
            },
        },
        {
            "product_code":
                "predictive_revenue_intelligence_os",
            "active": True,
            "binding_terms_ready": False,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
        },
        {
            "product_code":
                "predictive_revenue_autonomous_os",
            "active": True,
            "binding_terms_ready": False,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
        },
        {
            "product_code":
                "predictive_revenue_private_strategic",
            "active": True,
            "binding_terms_ready": False,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
        },
    ])

    return d


def test_product_bound_accounts_show_planning_value_not_pipeline_value():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=
            _catalog_with_locked_enterprise(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
        commercial_offer_book=_offer_book(),
    )

    product_bound = (
        board[
            "commercial_opportunities"
        ][
            "product_bound"
        ]
    )

    assert (
        product_bound[
            "account_count"
        ]
        == 2
    )

    assert (
        product_bound[
            "binding_count"
        ]
        == 2
    )

    assert (
        product_bound[
            "catalog_planning_mrr_if_one_unit_each_cents"
        ]
        == 199900
    )

    assert (
        product_bound[
            "catalog_planning_mrr_if_one_unit_each_usd"
        ]
        == 1999.0
    )

    assert (
        product_bound[
            "pipeline_value_cents"
        ]
        is None
    )

    assert (
        product_bound[
            "committed_mrr_cents"
        ]
        is None
    )

    assert all(
        row[
            "buyer_demand_verified"
        ]
        is False
        for row in product_bound[
            "bindings"
        ]
    )


def test_enterprise_hypotheses_remain_locked_and_unvalued():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=
            _catalog_with_locked_enterprise(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
        enterprise_targets=
            _enterprise_targets(),
    )

    enterprise = (
        board[
            "commercial_opportunities"
        ][
            "enterprise_locked"
        ]
    )

    assert (
        enterprise[
            "account_count"
        ]
        == 2
    )

    assert (
        enterprise[
            "locked_account_count"
        ]
        == 2
    )

    assert (
        enterprise[
            "planning_value_cents"
        ]
        is None
    )

    assert (
        enterprise[
            "committed_mrr_cents"
        ]
        is None
    )

    assert all(
        row[
            "product_state"
        ]
        == "LOCKED_PRODUCT_READINESS"
        for row in enterprise[
            "opportunities"
        ]
    )


def test_relationship_signals_do_not_become_revenue():
    board = build_revenue_capacity_board(
        revenue_pulse=_pulse(),
        revenue_command_queue=_queue(),
        commercial_catalog=
            _catalog_with_locked_enterprise(),
        stage2=_stage2(),
        commercial_exchange=_exchange(),
        pricing_policy=_pricing(),
        exchange_plan=_exchange_plan(),
        lead_smart_readiness={
            "buyer": "Lead Smart",
            "mode": "PREACTIVATION",
            "launch_ready": False,
            "blockers": [
                "routing_runtime_verified"
            ],
        },
        connexis_checkpoint={
            "recorded_at":
                "2026-10-02T10:16:55+00:00",
            "conversation_evidence": {
                "connexis_genuine_decision_maker_reply":
                    True,
                "connexis_buy_box_details_received":
                    False,
            },
            "next_action":
                "obtain explicit terms",
        },
    )

    relationships = (
        board[
            "commercial_opportunities"
        ][
            "relationship_signals"
        ]
    )

    assert (
        relationships[
            "signal_count"
        ]
        == 2
    )

    assert (
        relationships[
            "signals_are_pipeline_revenue"
        ]
        is False
    )

    assert (
        relationships[
            "signals_are_committed_mrr"
        ]
        is False
    )
