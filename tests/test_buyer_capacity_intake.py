from empire_os.buyer_capacity_intake import parse_buyer_capacity_reply


def test_complete_capacity_claim_is_explicit_and_bounded():
    result = parse_buyer_capacity_reply(
        "We cover Austin and Round Rock. We can handle 10-15 leads per day. "
        "Webhook is our preferred delivery route: https://acme.test/leads"
    )
    assert result["state"] == "complete"
    assert result["territory"] == "Austin and Round Rock"
    assert result["daily_cap"] == 10
    assert result["delivery_route"] == "webhook"
    assert result["delivery_reference"] == "https://acme.test/leads"
    assert result["evidence"]["capacity_high"] == 15
    assert result["evidence"]["capacity_policy"] == (
        "lower_bound_for_bounded_planning"
    )
    assert result["evidence"]["binding_commercial_terms"] is False


def test_partial_claim_does_not_infer_missing_fields():
    result = parse_buyer_capacity_reply(
        "We can take 8 qualified opportunities per day."
    )
    assert result["state"] == "partial"
    assert result["daily_cap"] == 8
    assert result["territory"] is None
    assert result["delivery_route"] is None


def test_ambiguous_delivery_route_is_not_guessed():
    result = parse_buyer_capacity_reply(
        "Our territory is Dallas. We can handle 12 leads per day. "
        "Email or webhook could work."
    )
    assert result["state"] == "partial"
    assert result["delivery_route"] is None
    assert result["evidence"]["delivery_ambiguous"] is True
    assert result["evidence"]["delivery_options"] == ["webhook", "email"]


def test_empty_reply_has_no_capacity_evidence():
    result = parse_buyer_capacity_reply("")
    assert result["has_explicit_capacity_evidence"] is False
    assert result["state"] == "none"
