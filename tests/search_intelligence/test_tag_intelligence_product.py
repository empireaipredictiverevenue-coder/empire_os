from empire_os.search_intelligence.products import (
    get_search_product,
)


def test_tag_intelligence_monitor_is_recurring_sellable_product():
    product = get_search_product("tag_intelligence_monitor")

    assert product is not None
    assert product.commercial_model == "monthly_subscription"
    assert "subscription" in product.revenue_models
    assert "agency_reseller_wholesale" in product.revenue_models
    assert "white_label_license" in product.revenue_models
    assert "multi_site_monitoring" in product.revenue_models
    assert "tag_intelligence" in product.required_capabilities
    assert product.execution_mode == "OBSERVE"
    assert product.publishing_authority is False


def test_tag_intelligence_monitor_covers_search_and_measurement_surfaces():
    product = get_search_product("tag_intelligence_monitor")

    deliverables = set(product.deliverables)
    assert "title_meta_canonical_robots_health" in deliverables
    assert "meta_pixel_and_capi_health" in deliverables
    assert "google_tag_gtm_ga4_health" in deliverables
    assert "conversion_event_integrity" in deliverables
    assert "consent_configuration_review" in deliverables
    assert "revenue_truth_attribution_linkage" in deliverables
