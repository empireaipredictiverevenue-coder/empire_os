from empire_os.lead_smart_ringba_api_observer import (
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_TRACKING_NUMBER,
    build_schema_observation,
    extract_rows,
)


def fixture():
    return {
        "result": {
            "callLog": {
                "data": [
                    {
                        "columns": [
                            {
                                "name":
                                    "inboundCallId",
                                "value":
                                    "call-001",
                            },
                            {
                                "name":
                                    "number",
                                "value":
                                    EXPECTED_TRACKING_NUMBER,
                            },
                            {
                                "name":
                                    "callConnectionLength",
                                "value": 121,
                            },
                        ],
                        "tags": [
                            {
                                "name":
                                    "CampaignId",
                                "value":
                                    EXPECTED_CAMPAIGN_ID,
                            },
                            {
                                "name":
                                    "Zip",
                                "value":
                                    "07006",
                            },
                            {
                                "name":
                                    "CallerNumber",
                                "value":
                                    "+15555550123",
                            },
                        ],
                        "events": [
                            {
                                "eventName":
                                    "CompletedCall",
                                "foo":
                                    "bar",
                            },
                        ],
                    }
                ]
            }
        }
    }


def test_extract_rows_handles_ringba_calllog_shape():
    rows = extract_rows(
        fixture()
    )

    assert len(rows) == 1


def test_schema_observation_matches_exact_campaign_and_number():
    result = build_schema_observation(
        account_id="RAexample",
        payload=fixture(),
    )

    assert (
        result[
            "raw_call_row_count"
        ]
        == 1
    )

    assert (
        result[
            "exact_campaign_and_number_match_count"
        ]
        == 1
    )

    assert (
        result[
            "raw_response_persisted"
        ]
        is False
    )

    assert (
        result[
            "caller_phone_persisted"
        ]
        is False
    )

    assert (
        result[
            "normalization_performed"
        ]
        is False
    )

    assert (
        result[
            "revenue_recognized"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )


def test_sanitized_match_does_not_persist_caller_number():
    result = build_schema_observation(
        account_id="RAexample",
        payload=fixture(),
    )

    text = str(
        result[
            "exact_matches"
        ]
    )

    assert "+15555550123" not in text


def test_schema_keys_are_observed_without_promoting_payout():
    result = build_schema_observation(
        account_id="RAexample",
        payload=fixture(),
    )

    assert (
        "callConnectionLength"
        in result["column_keys"]
    )

    assert (
        "CampaignId"
        in result["tag_keys"]
    )

    assert (
        "CompletedCall"
        in result["event_names"]
    )

    assert (
        result[
            "payout_truth_promoted"
        ]
        is False
    )


def test_recent_calllogs_use_modern_report_endpoint(
    monkeypatch,
):
    import empire_os.lead_smart_ringba_api_observer as module

    seen = {}

    def fake_request(**kwargs):
        seen.update(kwargs)

        return (
            200,
            {
                "report": {
                    "records": []
                }
            },
        )

    monkeypatch.setattr(
        module,
        "_json_request",
        fake_request,
    )

    result, negotiation = (
        module.fetch_recent_call_logs(
            token="not-real",
            account_id="RAexample",
        )
    )

    assert result == {
        "report": {
            "records": []
        }
    }

    assert (
        negotiation[
            "minimum_identity_contract_ready"
        ]
        is True
    )

    assert (
        negotiation[
            "caller_ani_requested"
        ]
        is False
    )

    assert (
        seen["url"]
        ==
        "https://api.ringba.com/"
        "v2/RAexample/calllogs"
    )

    assert seen["method"] == "POST"

    payload = seen["payload"]

    assert "reportStart" in payload
    assert "reportEnd" in payload
    assert payload["offset"] == 0
    assert payload["size"] == 50

    requested = {
        row["column"]
        for row in payload[
            "valueColumns"
        ]
    }

    assert "campaignId" in requested
    assert "inboundCallId" in requested
    assert "number" in requested

    assert (
        "connectedCallLengthInSeconds"
        in requested
    )

    assert "payoutAmount" in requested
    assert "isDuplicate" in requested

    # Caller ANI must not be requested.
    assert "inboundPhoneNumber" not in requested


def test_affiliate_role_optional_column_is_removed_only_when_provider_says_so(
    monkeypatch,
):
    import empire_os.lead_smart_ringba_api_observer as module

    calls = []

    def fake_request(**kwargs):
        calls.append(kwargs)

        requested = {
            row["column"]
            for row in kwargs[
                "payload"
            ]["valueColumns"]
        }

        if (
            "tag:Geo:ZipCode"
            in requested
        ):
            raise module.RingbaApiError(
                "Ringba HTTP 422: "
                '{"isSuccessful":false,'
                '"message":"Value column '
                'tag:Geo:ZipCode is not '
                'available for this '
                'role(affiliate)"}'
            )

        return (
            200,
            {
                "report": {
                    "records": []
                }
            },
        )

    monkeypatch.setattr(
        module,
        "_json_request",
        fake_request,
    )

    payload, negotiation = (
        module.fetch_recent_call_logs(
            token="not-real",
            account_id="RAexample",
        )
    )

    assert payload == {
        "report": {
            "records": []
        }
    }

    assert len(calls) == 2

    assert (
        negotiation["api_role"]
        == "affiliate"
    )

    assert (
        negotiation[
            "role_restricted_columns"
        ]
        == ["tag:Geo:ZipCode"]
    )

    assert (
        "tag:Geo:ZipCode"
        not in negotiation[
            "successful_value_columns"
        ]
    )

    for required in (
        "campaignId",
        "inboundCallId",
        "number",
    ):
        assert (
            required
            in negotiation[
                "successful_value_columns"
            ]
        )


def test_required_identity_column_is_never_negotiated_away(
    monkeypatch,
):
    import empire_os.lead_smart_ringba_api_observer as module

    def fake_request(**kwargs):
        raise module.RingbaApiError(
            "Ringba HTTP 422: "
            '{"message":"Value column '
            'campaignId is not available '
            'for this role(affiliate)"}'
        )

    monkeypatch.setattr(
        module,
        "_json_request",
        fake_request,
    )

    import pytest

    with pytest.raises(
        module.RingbaApiError,
        match="required Ringba identity",
    ):
        module.fetch_recent_call_logs(
            token="not-real",
            account_id="RAexample",
        )


def test_tracking_number_matches_e164_or_digits_only():
    import empire_os.lead_smart_ringba_api_observer as module

    payload = {
        "report": {
            "records": [
                {
                    "campaignId":
                        module.EXPECTED_CAMPAIGN_ID,

                    "inboundCallId":
                        "RGB-test",

                    # Ringba may omit "+".
                    "number":
                        "18883579305",

                    "callDt":
                        "2026-10-06T15:00:00Z",

                    "payoutAmount":
                        0,
                }
            ]
        }
    }

    result = module.build_schema_observation(
        account_id="RAexample",
        payload=payload,
    )

    assert (
        result[
            "tracking_number_match_count"
        ]
        == 1
    )

    assert (
        result[
            "campaign_id_match_count"
        ]
        == 1
    )

    assert (
        result[
            "exact_campaign_and_number_match_count"
        ]
        == 1
    )
