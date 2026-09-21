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
