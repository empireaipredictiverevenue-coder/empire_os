from empire_os.lead_sources import overpass


def test_query_uses_supported_craft_alternatives():
    query = overpass._query(
        30.267153,
        -97.743057,
        radius=1000,
    )

    assert '["craft"~"^(' in query

    for craft in overpass.CRAFT_TO_NICHE:
        assert craft in query

    assert "node" in query
    assert "way" in query
    assert "relation" in query
    assert "around:1000,30.267153,-97.743057" in query

    # Regression: old query accidentally chained unrelated tag keys.
    assert ']["' not in query


def test_element_maps_roofer_to_real_business_candidate():
    candidate = overpass._element_to_candidate({
        "type": "node",
        "id": 123456,
        "lat": 30.25,
        "lon": -97.75,
        "tags": {
            "name": "Austin Roof Works",
            "craft": "roofer",
            "phone": "+1 512 555 0101",
            "website": "https://austinroof.example",
            "email": "hello@austinroof.example",
            "addr:housenumber": "10",
            "addr:street": "Main St",
            "addr:city": "Austin",
            "addr:state": "TX",
            "addr:postcode": "78701",
        },
    })

    assert candidate is not None
    assert candidate.name == "Austin Roof Works"
    assert candidate.niche == "roofing"
    assert candidate.source == "overpass_osm"

    # Provenance must point to OSM, not silently become website identity.
    assert (
        candidate.url
        == "https://www.openstreetmap.org/node/123456"
    )
    assert (
        candidate.raw["business_website"]
        == "https://austinroof.example"
    )

    assert candidate.phone == "+1 512 555 0101"
    assert candidate.email == "hello@austinroof.example"
    assert candidate.state == "TX"


def test_element_rejects_non_contactable_business():
    candidate = overpass._element_to_candidate({
        "type": "node",
        "id": 999,
        "tags": {
            "name": "No Contact Roofing",
            "craft": "roofer",
        },
    })

    assert candidate is None


def test_element_rejects_unsupported_craft():
    candidate = overpass._element_to_candidate({
        "type": "node",
        "id": 999,
        "tags": {
            "name": "Random Business",
            "craft": "unknown_trade",
            "phone": "555-0101",
        },
    })

    assert candidate is None


def test_unknown_metro_fails_closed(monkeypatch):
    monkeypatch.setattr(
        overpass,
        "_fetch",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unknown metro must never fetch")
        ),
    )

    assert list(
        overpass.run("Not A Real Metro")
    ) == []


def test_run_sets_requested_metro(monkeypatch):
    candidate = overpass._element_to_candidate({
        "type": "node",
        "id": 123,
        "tags": {
            "name": "Austin Electric",
            "craft": "electrician",
            "phone": "512-555-0123",
        },
    })

    monkeypatch.setattr(
        overpass,
        "_fetch",
        lambda lat, lon: [candidate],
    )
    monkeypatch.setattr(
        overpass.time,
        "sleep",
        lambda seconds: None,
    )

    results = list(
        overpass.run("Austin, TX")
    )

    assert len(results) == 1
    assert results[0].metro == "Austin, TX"
    assert results[0].niche == "electrical"
