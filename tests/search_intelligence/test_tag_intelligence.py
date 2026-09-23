from empire_os.tag_intelligence import review_tag_intelligence


def test_search_and_social_tags_are_reviewed_together():
    result = review_tag_intelligence(
        page_tags={
            "url": "https://example.com/service",
            "title": "",
            "meta_description": "",
            "canonical_url": "",
            "robots": "index,follow",
            "open_graph": {},
            "twitter": {},
            "json_ld_types": [],
            "meta_keywords_present": True,
        },
        expectations={
            "intended_public": True,
            "schema_expected": True,
        },
    )

    codes = {issue.code for issue in result.issues}
    assert "missing_title" in codes
    assert "missing_meta_description" in codes
    assert "missing_canonical" in codes
    assert "missing_og_title" in codes
    assert "structured_data_missing" in codes
    assert "meta_keywords_ignored" in codes
    assert result.execution_authority == "none"
    assert result.automatic_tag_mutation is False
    assert result.estimated_revenue_loss_cents is None


def test_public_noindex_is_critical_but_not_auto_fixed():
    result = review_tag_intelligence(
        page_tags={
            "url": "https://example.com/money-page",
            "title": "Money Page",
            "meta_description": "Useful page",
            "canonical_url": "https://example.com/money-page",
            "robots": "noindex,follow",
            "open_graph": {
                "title": "Money Page",
                "description": "Useful page",
                "url": "https://example.com/money-page",
                "image": "https://example.com/image.jpg",
            },
            "twitter": {"card": "summary_large_image"},
        },
        expectations={"intended_public": True},
    )

    issue = next(
        row for row in result.issues
        if row.code == "public_page_noindex"
    )
    assert issue.severity == "critical"
    assert issue.manual_review_required is True
    assert issue.execution_allowed is False


def test_meta_pixel_and_capi_require_verified_event_dedup():
    result = review_tag_intelligence(
        measurement_tags={
            "meta_pixel_ids": ["123456"],
            "meta_capi_enabled": True,
            "meta_event_id_dedup": False,
        },
        expectations={"meta_ads_expected": True},
    )

    issue = next(
        row for row in result.issues
        if row.code == "meta_pixel_capi_dedup_unverified"
    )
    assert issue.severity == "critical"
    assert result.actual_revenue_impact_known is False


def test_measurement_stack_detects_missing_and_duplicate_events():
    result = review_tag_intelligence(
        measurement_tags={
            "google_tag_ids": ["GT-AAA"],
            "gtm_container_ids": ["GTM-AAA"],
            "ga4_measurement_ids": ["G-AAA"],
            "google_ads_conversion_ids": ["AW-AAA"],
            "observed_events": ["page_view", "generate_lead"],
            "duplicate_event_counts": {"generate_lead": 2},
            "duplicate_tag_counts": {"GTM-AAA": 2},
            "consent_mode_enabled": None,
            "revenue_truth_linked": False,
        },
        expectations={
            "google_analytics_expected": True,
            "google_ads_expected": True,
            "required_events": ["page_view", "generate_lead", "purchase"],
            "consent_review_required": True,
            "revenue_attribution_expected": True,
        },
    )

    codes = [issue.code for issue in result.issues]
    assert "required_conversion_event_missing" in codes
    assert "duplicate_conversion_event" in codes
    assert "duplicate_measurement_tag" in codes
    assert "consent_configuration_unverified" in codes
    assert "revenue_truth_link_missing" in codes
    assert result.estimated_revenue_loss_cents is None
    assert result.compliance_status == "UNKNOWN"


def test_clean_observed_stack_does_not_invent_problems():
    result = review_tag_intelligence(
        page_tags={
            "url": "https://example.com/",
            "title": "Example",
            "meta_description": "Example description",
            "canonical_url": "https://example.com/",
            "robots": "index,follow",
            "open_graph": {
                "title": "Example",
                "description": "Example description",
                "url": "https://example.com/",
                "image": "https://example.com/image.jpg",
            },
            "twitter": {"card": "summary_large_image"},
            "json_ld_types": ["Organization"],
            "viewport_present": True,
            "charset_present": True,
            "h1_count": 1,
            "images_missing_alt": 0,
        },
        measurement_tags={
            "google_tag_ids": ["GT-AAA"],
            "gtm_container_ids": ["GTM-AAA"],
            "ga4_measurement_ids": ["G-AAA"],
            "google_ads_conversion_ids": ["AW-AAA"],
            "meta_pixel_ids": ["123"],
            "meta_capi_enabled": True,
            "meta_event_id_dedup": True,
            "observed_events": ["page_view", "generate_lead"],
            "consent_mode_enabled": True,
            "server_side_tagging": True,
            "revenue_truth_linked": True,
        },
        expectations={
            "intended_public": True,
            "schema_expected": True,
            "google_analytics_expected": True,
            "google_ads_expected": True,
            "meta_ads_expected": True,
            "required_events": ["page_view", "generate_lead"],
            "consent_review_required": True,
            "server_side_tagging_expected": True,
            "revenue_attribution_expected": True,
        },
    )

    assert result.issues == ()
    assert result.repair_priority_score == 0
