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
