from scripts.materialize_lead_smart_roofing_pilot import build_review


def review():
    return build_review()


def test_materializer_uses_confirmed_gmail_evidence():
    result = review()

    assert result["source_ref"] == "gmail:1a10c6b2530f2951"
    assert result["commercial_truth"]["offer_name"] == (
        "Main Roofing Contractors - Nationwide - Variable Rate"
    )


def test_materializer_preserves_confirmed_call_rules():
    truth = review()["commercial_truth"]

    assert truth["organic_seo_approved"] is True
    assert truth["qualification_seconds"] is None
    assert truth["qualification_seconds_min"] == 60
    assert truth["qualification_seconds_max"] == 120
    assert truth["qualification_route_dependent"] is True
    assert truth["appointment_cpl_possible"] is True
    assert truth["caller_requirement"] == "homeowner"
    assert truth["geography_requirement"] == "covered_zip"
    assert truth["duplicate_window_days"] == 30
    assert truth["duplicate_pays_once"] is True
    assert truth["capacity_mode"] == "uncapped"
    assert truth["daily_cap"] is None


def test_materializer_preserves_dynamic_payout_unknown():
    truth = review()["commercial_truth"]

    assert truth["pricing_mode"] == "live_bid_at_call_time"
    assert truth["payout"] is None
    assert truth["currency"] is None
    assert truth["payout_verified"] is False


def test_materializer_preserves_ringba_runtime_blockers():
    result = review()
    truth = result["commercial_truth"]

    assert truth["routing_platform"] == "Ringba"
    assert truth["tracking_number_assigned"] is True
    assert truth["tracking_number"] == "+18883579305"
    assert truth["tracking_verified"] is False
    assert truth["routing_verified"] is False

    assert result["ringba_offer_applied"] is True
    assert result["ringba_offer_approved"] is True
    assert truth["offer_application_status"] == "approved"
    assert truth["offer_application_approved"] is True
    assert truth["ringba_offer_label"] == "Roofing - Nationwide"
    assert (
        truth["ringba_campaign_id"]
        == "CA8278ed3f26e9495b881fe3833174d007"
    )
    assert (
        truth["offer_approval_source_ref"]
        == "gmail:1a1112c17349445a"
    )

    # Approval does not cross the execution boundary.
    assert result["tracking_bound"] is False
    assert result["routing_enabled"] is False


def test_materializer_exposes_buyer_rtb_requirements_without_promoting_routing():
    result = review()
    truth = result["commercial_truth"]
    assert truth["buyer_route_report"]["source_ref"] == "gmail:1a121bc6211d60b7"
    assert truth["buyer_route_report"]["independently_verified"] is False
    assert truth["rtb_transport_requirements"]["zipcode_required"] is True
    assert truth["rtb_transport_requirements"]["expose_caller_id"] == "yes"
    assert truth["rtb_transport_requirements"]["transport_implemented"] is False
    assert truth["rtb_enabled"] is False
    assert truth["routing_verified"] is False
    assert result["traffic_enabled"] is False


def test_materializer_never_authorizes_traffic():
    result = review()

    assert result["traffic_enabled"] is False
    assert result["commercial_activation_authorized"] is False
    assert result["execution_authority"] == "none"

    assert result["supply_review"]["live_traffic_authorized"] is False
    assert (
        result["supply_review"]["commercial_activation_authorized"]
        is False
    )


def test_current_supply_blockers_are_truthful():
    result = review()
    blockers = set(result["supply_review"]["blockers"])

    assert "traffic_source_buyer_approval" not in blockers

    # Buyer approved the supplied paid-search copy, but explicit evidence
    # for site and landing-page review remains absent.
    assert "ads_reviewed" not in blockers
    assert "sites_reviewed" in blockers
    assert "landing_pages_reviewed" in blockers

    # Buyer verified the dynamic live-bid pricing mechanism.
    # No concrete call payout has yet been observed or invented.
    assert "dynamic_payout_verification" not in blockers
    assert result["policy"]["pricing"]["mechanism_verified"] is True
    assert result["policy"]["pricing"]["actual_payout_observed"] is False
    assert result["policy"]["pricing"]["payout_value"] is None
    assert result["policy"]["pricing"]["currency"] is None
    assert result["policy"]["pricing"]["verified"] is False

    # RTB remains an available alternative, but the confirmed pilot
    # explicitly selects Direct. Unverified RTB terms therefore do not
    # block the selected route.
    assert "rtb_terms_verification" not in blockers
    assert result["policy"]["routing"]["selected_mode"] == "direct"
    assert result["policy"]["routing"]["rtb_supported"] is True
    assert result["policy"]["routing"]["rtb_terms_verified"] is False


def test_ringba_observed_offer_truth_and_authority_boundary():
    from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy

    p = lead_smart_confirmed_roofing_policy(source_ref="gmail:1a10c6b2530f2951")
    r = p["routing"]
    c = p["conversion"]

    assert r["ringba_campaign_id"] ==         "CA8278ed3f26e9495b881fe3833174d007"

    assert r["tracking_number_assigned"] is True
    assert r["tracking_number"] == "+18883579305"

    assert r["payout_model"] == "VARIABLE_RATE"
    assert r["payout_currency"] == "USD"
    assert r["observed_payout_min"] == 5
    assert r["observed_payout_max"] == 150

    # Percentage was not visible in supplied Ringba evidence.
    assert r["revshare_percentage"] is None
    assert r["rtb_enabled"] is False

    assert c["qualification_seconds"] is None
    assert c["qualification_seconds_min"] == 60
    assert c["qualification_seconds_max"] == 120
    assert c["qualification_route_dependent"] is True
    assert c["appointment_cpl_possible"] is True

    assert r["max_tracking_numbers_without_prior_discussion"] == 5
    assert r["zip_coverage_required"] is True

    assert r["facebook_marketplace_allowed"] is False
    assert r["free_quote_claim_allowed"] is False
    assert r["free_estimate_claim_allowed"] is False
    assert r["fake_or_ai_generated_reviews_allowed"] is False

    # Assignment cannot grant execution authority.
    assert r.get("tracking_verified", False) is False
    assert r.get("routing_verified", False) is False
    assert r.get("routing_enabled", False) is False
    assert r.get("traffic_enabled", False) is False

    assert p.get("execution_authority") in (None, "none", "NONE")


def test_lead_smart_support_evidence_flows_to_commercial_truth_without_activation():
    result = review()
    truth = result["commercial_truth"]
    assert truth["operating_hours_confirmation"]["source_ref"] == (
        "gmail:1a12229d9d3ffe75"
    )
    assert truth["operating_hours_confirmation"]["zone_name"] == "America/Chicago"
    assert truth["direct_route_requirements"]["direct_ivr_collects_zip"] is True
    assert truth["direct_route_requirements"]["caller_id_pass_through_verified"] is False
    assert truth["landing_review_report"]["approved"] is False
    assert result["traffic_enabled"] is False
    assert result["execution_authority"] == "none"
