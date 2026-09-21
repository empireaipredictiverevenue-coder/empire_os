from empire_os.control_fabric import EventEnvelope, default_registry, route_event


def test_storm_event_routes_to_acquisition():
    routes = route_event(EventEnvelope(
        event_type="storm_opportunity_detected",
        source="storm_service",
        commercial_priority=95,
    ))
    assert routes[0]["component"] == "acquisition"
    assert routes[0]["authority"] == "internal_write"
    assert routes[0]["commercial_priority"] == 95


def test_registry_has_reliability_components():
    names = {spec.name for spec in default_registry()}
    assert {"ops_sentinel", "ops_healer", "revenue_pulse", "gtm"} <= names


def test_unknown_event_routes_nowhere():
    assert route_event({"event_type": "not_registered"}) == []
