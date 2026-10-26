from empire_os.buyer_commercial_terms_intake import parse_buyer_stated_price


def test_explicit_price_per_lead_is_captured():
    result = parse_buyer_stated_price(
        "We can take 10 leads per day and pay $75 per lead."
    )
    assert result["has_explicit_price_evidence"] is True
    assert result["amount_cents"] == 7500
    assert result["unit"] == "per_lead"
    assert result["evidence"]["source_type"] == "buyer_stated"
    assert result["evidence"]["binding"] is False
    assert result["evidence"]["verified"] is False


def test_explicit_price_per_call_is_captured():
    result = parse_buyer_stated_price("Our rate is $42.50 per call.")
    assert result["has_explicit_price_evidence"] is True
    assert result["amount_cents"] == 4250
    assert result["unit"] == "per_call"


def test_unrelated_money_does_not_become_price():
    result = parse_buyer_stated_price(
        "Our monthly budget is $5000 and we can take 8 leads per day."
    )
    assert result["has_explicit_price_evidence"] is False


def test_multiple_different_prices_fail_closed():
    result = parse_buyer_stated_price(
        "We pay $70 per lead for roofing and $90 per lead for solar."
    )
    assert result["has_explicit_price_evidence"] is False
    assert result["evidence"]["ambiguous"] is True


def test_empty_text_has_no_price_evidence():
    result = parse_buyer_stated_price("")
    assert result["has_explicit_price_evidence"] is False


def test_buyer_proposed_qualified_call_price_recognised_but_not_binding():
    # Exact commercial syntax in the real DemandCalls supplier proposal.
    text = "We're happy to start at $50 per qualified call for your initial pilot."
    result = parse_buyer_stated_price(text)
    assert result["has_explicit_price_evidence"] is True
    assert result["amount_cents"] == 5000
    assert result["unit"] == "per_call"
    assert result["evidence"]["source_type"] == "buyer_stated"
    assert result["evidence"]["binding"] is False
    assert result["evidence"]["verified"] is False
    assert result["evidence"]["actual_revenue"] is False


def test_qualified_accepted_call_and_lead_are_supported_with_no_inferred_contract():
    for sentence, cents, unit in (
        ("We propose USD $50 per qualified accepted call.", 5000, "per_call"),
        ("Rate: $25 per billable connected call", 2500, "per_call"),
        ("Our rate is $90 per qualified lead.", 9000, "per_lead"),
    ):
        parsed = parse_buyer_stated_price(sentence)
        assert parsed["has_explicit_price_evidence"] is True
        assert parsed["amount_cents"] == cents
        assert parsed["unit"] == unit
        assert parsed["evidence"]["binding"] is False


def test_supplier_price_band_is_not_promoted_to_fixed_amount():
    for sentence in (
        "Payouts range from $25–$75 per qualified call depending on geography.",
        "Rate $25-$75 per qualified call.",
        "Between $25 to $75 per billable call.",
    ):
        result = parse_buyer_stated_price(sentence)
        assert result["has_explicit_price_evidence"] is False
        assert result["amount_cents"] is None


def test_negative_price_offers_are_not_positive_evidence():
    for sentence in (
        "We do not offer $50 per call.",
        "We do not pay $50 per accepted call.",
        "No $50 per call.",
    ):
        result = parse_buyer_stated_price(sentence)
        assert result["has_explicit_price_evidence"] is False


def test_conflicting_fixed_prices_still_fail_closed():
    result = parse_buyer_stated_price(
        "We offer $50 per qualified call for California but $75 per call in Florida."
    )
    assert result["has_explicit_price_evidence"] is False
    assert result["evidence"]["ambiguous"] is True
