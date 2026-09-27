from scripts.aeo_metro_gen import generate_page


def test_premium_page_has_no_legacy_claims_or_dead_endpoint():
    page = generate_page("roofing", "DFW")
    lowered = page.lower()
    assert "leads today" not in lowered
    assert "updated every 6 hours" not in lowered
    assert "$240/mo" not in lowered
    assert "within the hour" not in lowered
    assert "/v1/leads/direct" not in lowered
    assert "exclusive leads" not in lowered
    assert "<form" not in lowered


def test_premium_page_has_operator_value_and_valid_css_braces():
    page = generate_page("roofing", "DFW")
    assert "Roofing demand intelligence for Dallas-Fort Worth." in page
    assert "Observed first. Modelled clearly labelled." in page
    assert "Signal to action, without blurring the truth." in page
    assert ":root {{" not in page
    assert "body {{" not in page
    assert "@media(max-width:900px){{" not in page


def test_premium_page_uses_webpage_service_schema_not_fake_local_business():
    page = generate_page("roofing", "DFW")
    assert '"@type":"WebPage"' in page
    assert '"@type":"Service"' in page
    assert '"@type":"LocalBusiness"' not in page
