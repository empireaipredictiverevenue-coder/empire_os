import empire_os.lead_smart_ringba_tracking_observer as module


def test_direct_campaign_binding_requires_campaign_and_number(
    monkeypatch,
):
    responses = {
        "campaigns/"
        + module.EXPECTED_CAMPAIGN_ID: {
            "id":
                module.EXPECTED_CAMPAIGN_ID,

            "publishers": [
                {
                    "number":
                        module.EXPECTED_TRACKING_NUMBER,
                }
            ],
        },

        "/campaigns": [],

        "/numbers": [],
    }

    def fake_get(
        *,
        token,
        url,
    ):
        for suffix, payload in (
            responses.items()
        ):
            if url.endswith(suffix):
                return {
                    "status": 200,
                    "accessible": True,
                    "payload": payload,
                }

        raise AssertionError(url)

    monkeypatch.setattr(
        module,
        "_probe_get",
        fake_get,
    )

    result = (
        module.observe_tracking_objects(
            token="secret",
            account_id="RAexample",
        )
    )

    assert (
        result[
            "direct_campaign_binding"
        ]
        is True
    )

    assert (
        result[
            "provider_binding_verified"
        ]
        is True
    )

    assert (
        result[
            "tracking_verification_candidate"
        ]
        is True
    )

    assert (
        result[
            "tracking_verified_change"
        ]
        is False
    )


def test_number_inbound_reference_can_prove_binding(
    monkeypatch,
):
    number_id = "PN123"

    def fake_probe(
        *,
        token,
        url,
    ):
        if url.endswith(
            "/campaigns/"
            + module.EXPECTED_CAMPAIGN_ID
        ):
            return {
                "status": 403,
                "accessible": False,
                "error_class":
                    "FORBIDDEN",
                "payload": None,
            }

        if url.endswith(
            "/campaigns"
        ):
            return {
                "status": 403,
                "accessible": False,
                "error_class":
                    "FORBIDDEN",
                "payload": None,
            }

        if url.endswith(
            "/numbers"
        ):
            return {
                "status": 200,
                "accessible": True,
                "payload": [
                    {
                        "id":
                            number_id,

                        "number":
                            "18883579305",

                        "isActive":
                            True,
                    }
                ],
            }

        if url.endswith(
            "/numbers/"
            + number_id
            + "/InboundReferences"
        ):
            return {
                "status": 200,
                "accessible": True,
                "payload": [
                    {
                        "campaignId":
                            module.EXPECTED_CAMPAIGN_ID,
                    }
                ],
            }

        raise AssertionError(url)

    monkeypatch.setattr(
        module,
        "_probe_get",
        fake_probe,
    )

    result = (
        module.observe_tracking_objects(
            token="secret",
            account_id="RAexample",
        )
    )

    assert (
        result[
            "number_object_found"
        ]
        is True
    )

    assert (
        result[
            "inbound_reference_binding"
        ]
        is True
    )

    assert (
        result[
            "provider_binding_verified"
        ]
        is True
    )


def test_number_without_campaign_reference_does_not_verify():
    payload = [
        {
            "id": "PN123",
            "number":
                module.EXPECTED_TRACKING_NUMBER,
        }
    ]

    row, ident = (
        module.locate_target_number(
            payload
        )
    )

    assert row is not None
    assert ident == "PN123"

    assert (
        module._contains_exact_campaign(
            payload
        )
        is False
    )


def test_tracking_number_matches_digit_variants():
    for value in (
        "+18883579305",
        "18883579305",
        "8883579305",
        "(888) 357-9305",
    ):
        assert (
            module._contains_tracking_number(
                value
            )
            is True
        )


def test_unrelated_numbers_are_not_matches():
    assert (
        module._contains_tracking_number(
            "+12125551212"
        )
        is False
    )
