import empire_os.lead_smart_ringba_routing_observer as module


def test_campaign_route_structure_is_observed_but_not_runtime_verified(
    monkeypatch,
):
    def fake_probe(
        *,
        token,
        url,
    ):
        if "/campaigns/" in url:
            return {
                "status": 200,
                "accessible": True,
                "error_class": None,
                "payload": {
                    "id":
                        module.EXPECTED_CAMPAIGN_ID,

                    "callRoutes": [
                        {
                            "id":
                                "route-secret-id",

                            "enabled":
                                True,

                            "priority":
                                1,

                            "callTarget": {
                                "id":
                                    "target-secret-id",
                            },
                        }
                    ],
                },
            }

        if url.endswith(
            "/CallRoutes"
        ):
            return {
                "status": 403,
                "accessible": False,
                "error_class":
                    "FORBIDDEN",
                "payload": None,
            }

        raise AssertionError(url)

    monkeypatch.setattr(
        module,
        "_probe_get",
        fake_probe,
    )

    result = (
        module.observe_routing_objects(
            token="secret",
            account_id="RAexample",
        )
    )

    assert (
        result[
            "campaign_detail"
        ][
            "campaign_identity_verified"
        ]
        is True
    )

    assert (
        result[
            "routing_configuration_observed"
        ]
        is True
    )

    assert (
        result[
            "campaign_route_object_count"
        ]
        >= 1
    )

    assert (
        result[
            "campaign_enabled_route_candidate_count"
        ]
        >= 1
    )

    assert result["route_visibility"] == {
        "enumeration_accessible": False,
        "limited_by_http_403": True,
        "scope": "FORBIDDEN_NO_ROUTE_ABSENCE_INFERENCE",
        "buyer_route_absence_proven": False,
        "buyer_route_live_proven": False,
        "independent_call_test_required": True,
    }
    assert (
        result[
            "routing_runtime_verified"
        ]
        is False
    )

    assert (
        result[
            "test_call_performed"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )


def test_route_sanitizer_does_not_persist_raw_route_or_target_ids():
    payload = {
        "callRoutes": [
            {
                "id":
                    "route-secret-id",

                "enabled":
                    True,

                "callTarget": {
                    "id":
                        "target-secret-id",
                },
            }
        ]
    }

    rows = (
        module.collect_route_objects(
            payload
        )
    )

    text = str(rows)

    assert (
        "route-secret-id"
        not in text
    )

    assert (
        "target-secret-id"
        not in text
    )

    assert rows


def test_no_route_structure_does_not_invent_configuration():
    rows = (
        module.collect_route_objects(
            {
                "id":
                    module.EXPECTED_CAMPAIGN_ID,

                "name":
                    "Roofing",
            }
        )
    )

    assert rows == []

def test_global_routes_empty_does_not_prove_live_connection(monkeypatch):
    def fake_probe(*, token, url):
        if "/campaigns/" in url:
            return {
                "status": 200, "accessible": True, "error_class": None,
                "payload": {"id": module.EXPECTED_CAMPAIGN_ID},
            }
        return {
            "status": 200, "accessible": True, "error_class": None,
            "payload": {"items": []},
        }
    monkeypatch.setattr(module, "_probe_get", fake_probe)
    result = module.observe_routing_objects(token="test", account_id="acct")
    assert result["route_visibility"]["enumeration_accessible"] is True
    assert result["route_visibility"]["limited_by_http_403"] is False
    assert result["route_visibility"]["scope"] == "OBSERVED_PROVIDER_SCOPE"
    assert result["route_visibility"]["buyer_route_live_proven"] is False
    assert result["route_visibility"]["buyer_route_absence_proven"] is False
    assert result["routing_runtime_verified"] is False
    assert result["traffic_enabled"] is False


def test_non403_unavailable_scope_also_fails_closed(monkeypatch):
    def fake_probe(*, token, url):
        if "/campaigns/" in url:
            return {
                "status": 200, "accessible": True, "error_class": None,
                "payload": {"id": module.EXPECTED_CAMPAIGN_ID},
            }
        return {
            "status": 404, "accessible": False, "error_class": "NOT_FOUND",
            "payload": None,
        }
    monkeypatch.setattr(module, "_probe_get", fake_probe)
    result = module.observe_routing_objects(token="test", account_id="acct")
    assert result["route_visibility"]["scope"] == "UNVERIFIED_API_SCOPE"
    assert result["route_visibility"]["buyer_route_absence_proven"] is False
    assert result["routing_enabled"] is False
