from empire_os.revenue_architecture_critic import review_revenue_architecture

def contract(**overrides):
    row={
        "single_control_plane":"autonomous_revenue_os",
        "timer_driven":False,
        "unknown_price_stays_null":True,
        "real_sources_only":True,
        "usdt_bsc_only":True,
        "lead_generation_batch":25,
        "qualification_batch":10,
        "external_send":False,
        "call_execution":False,
        "booking_execution":False,
        "binding_terms":False,
        "fund_movement":False,
        "revenue_recognition":False,
        "inventory_stages":(
            "RAW_LEAD","PREQUALIFIED_LEAD","QUALIFIED_CALL",
            "BOOKED_APPOINTMENT","CPA_OUTCOME",
        ),
    }
    row.update(overrides)
    return row

def test_clean_contract_passes():
    r=review_revenue_architecture(contract())
    assert r.passed is True
    assert r.blockers == ()
    assert r.execution_authority == "none"

def test_timer_driven_contract_blocks():
    r=review_revenue_architecture(contract(timer_driven=True))
    assert r.passed is False
    assert "timer_led_orchestration_not_allowed" in r.blockers

def test_unbounded_lead_batch_blocks():
    r=review_revenue_architecture(contract(lead_generation_batch=500))
    assert r.passed is False
    assert "lead_generation_batch_unbounded" in r.blockers

def test_external_execution_blocks():
    r=review_revenue_architecture(contract(external_send=True))
    assert r.passed is False
    assert "external_send_must_remain_gated" in r.blockers

def test_payment_rail_must_remain_usdt_bsc():
    r=review_revenue_architecture(contract(usdt_bsc_only=False))
    assert r.passed is False
    assert "canonical_payment_rail_not_enforced" in r.blockers
