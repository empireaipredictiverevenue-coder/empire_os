from empire_os.evidence_enrichment_planner import (
    plan_evidence_enrichment,
)


def test_sparse_prospect_prefers_bounded_site_probe():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "metro": "London",
    })

    assert plan["current_completeness"] == 15
    assert plan["current_evidence_confidence"] == 0.15
    assert plan["selected_actions"][0]["key"] == "first_party_site_probe"
    assert plan["selected_actions"][0]["target_fields"] == [
        "website",
        "email",
        "phone",
    ]
    assert plan["projected_completeness_upper_bound"] == 55
    assert plan["projected_confidence_upper_bound"] == 0.55
    assert plan["can_reach_target_with_available_actions"] is True
    assert plan["projection_is_not_observation"] is True


def test_existing_phone_reduces_site_probe_target():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "phone": "+442000000000",
    })

    action = plan["selected_actions"][0]
    assert action["target_fields"] == ["website", "email"]
    assert action["max_completeness_gain"] == 25
    assert plan["current_completeness"] == 30
    assert plan["projected_completeness_upper_bound"] == 55


def test_directory_profile_remains_missing_website_evidence():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "phone": "+18035551212",
        "website": (
            "https://www.bbb.org/us/nc/charlotte/profile/"
            "roofing-contractors/acme-roofing"
        ),
    })

    action = plan["selected_actions"][0]
    assert action["key"] == "first_party_site_probe"
    assert action["target_fields"] == ["website", "email"]
    assert plan["current_completeness"] == 30
    assert plan["current_evidence_confidence"] == 0.30


def test_existing_enough_evidence_needs_no_action():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "email": "owner@example.com",
        "phone": "+442000000000",
        "website": "https://example.com",
    })

    assert plan["current_completeness"] == 55
    assert plan["current_evidence_confidence"] == 0.55
    assert plan["selected_actions"] == []
    assert plan["can_reach_target_with_available_actions"] is True


def test_unavailable_future_actions_do_not_fake_reachability():
    plan = plan_evidence_enrichment(
        {
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "website": "https://example.com",
            "email": "owner@example.com",
        },
        target_confidence=0.80,
    )

    # Current bounded site capability can only add a missing phone (15 points).
    assert plan["selected_actions"][0]["key"] == "first_party_site_probe"
    assert plan["selected_actions"][0]["max_completeness_gain"] == 15
    assert plan["can_reach_target_with_available_actions"] is False

    future = {
        row["key"]: row
        for row in plan["all_candidate_actions"]
        if not row["available_now"]
    }
    assert "decision_maker_evidence" in future
    assert "registry_evidence" in future


def test_zero_values_are_preserved_as_observed_values():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "review_count": 0,
        "rating": 0,
    })

    # rating/review_count are not completeness fields and must not be invented
    # into the missing-field calculation.
    assert "rating" not in plan["missing_fields"]
    assert "review_count" not in plan["missing_fields"]


def test_plan_is_deterministic():
    prospect = {
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "phone": "+442000000000",
    }
    assert plan_evidence_enrichment(prospect) == plan_evidence_enrichment(
        prospect
    )


def test_invalid_target_confidence_rejected():
    for value in (0, -0.1, 1.1):
        try:
            plan_evidence_enrichment(
                {"business_name": "Acme"},
                target_confidence=value,
            )
        except ValueError as exc:
            assert "target_confidence" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_canonical_address_closes_street_gap():
    plan = plan_evidence_enrichment({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "address": "1 Test Street, London",
    })

    assert plan["current_completeness"] == 20
    assert "street" not in plan["missing_fields"]
