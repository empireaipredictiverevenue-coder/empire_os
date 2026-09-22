from empire_os.control_fabric import EventEnvelope, default_registry, route_event


def test_storm_event_routes_to_acquisition_and_opportunity_agent():
    routes = route_event(EventEnvelope(
        event_type="storm_opportunity_detected",
        source="storm_service",
        commercial_priority=95,
    ))
    by_component = {row["component"]: row for row in routes}
    assert "acquisition" in by_component
    assert "market_opportunity_agent" in by_component
    assert by_component["acquisition"]["authority"] == "internal_write"
    assert by_component["acquisition"]["commercial_priority"] == 95


def test_registry_has_reliability_components():
    names = {spec.name for spec in default_registry()}
    assert {"ops_sentinel", "ops_healer", "revenue_pulse", "gtm"} <= names


def test_unknown_event_routes_nowhere():
    assert route_event({"event_type": "not_registered"}) == []

def test_registry_has_opportunity_factory():
    names = {spec.name for spec in default_registry()}
    assert {"market_opportunity_agent", "opportunity_factory"} <= names


def test_opportunity_event_routes_to_factory():
    routes = route_event({
        "event_type": "opportunity_candidate_created",
        "commercial_priority": 88,
    })
    assert routes[0]["component"] == "opportunity_factory"
    assert routes[0]["commercial_priority"] == 88


def test_community_pain_routes_to_market_opportunity_agent():
    routes = route_event({
        "event_type": "community_pain_observed",
        "commercial_priority": 91,
    })
    assert routes
    assert routes[0]["component"] == "market_opportunity_agent"
    assert routes[0]["commercial_priority"] == 91


def test_opportunity_cycle_routes_to_canonical_loop():
    routes = route_event({
        "event_type": "opportunity_cycle_tick",
        "commercial_priority": 80,
    })
    assert routes
    assert routes[0]["component"] == "predictive_cloud_opportunity_loop"
    assert routes[0]["authority"] == "internal_write"


def test_executive_and_specialist_departments_are_registered():
    from empire_os.control_fabric import default_registry

    by_name = {row.name: row for row in default_registry()}
    for name in (
        "astra_executive",
        "commercial_product_catalog",
        "buyer_capacity_readiness",
        "fulfilment_readiness",
        "intelligence_fabric",
        "empire_coder",
    ):
        assert name in by_name
        assert by_name[name].authority == "internal_write"

    routes = route_event({
        "event_type": "build_complexity_evidence_required",
        "commercial_priority": 80,
    })
    assert routes[0]["component"] == "empire_coder"
