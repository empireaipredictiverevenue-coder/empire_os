from empire_os.predictive_revenue_enterprise_location import location_from_addresses


def test_location_from_first_party_us_address():
    out = location_from_addresses(["123 Main Street, Denver, CO 80202"])
    assert out["metro"] == "Denver, CO"
    assert out["state"] == "CO"
    assert out["location_verified"] is True


def test_location_missing_stays_unknown():
    assert location_from_addresses(["Call us today"]) is None


def test_location_rejects_street_fragment_as_city():
    assert location_from_addresses(["100 Piedmont Avenue Northeast Atlanta, GA 30303"]) is None
