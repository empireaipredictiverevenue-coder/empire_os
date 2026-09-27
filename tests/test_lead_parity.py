from empire_os.lead_parity import (
    LeadParityError,
    build_parity_report,
    fetch_canonical_parity_inputs,
)


def test_exact_uuid_and_external_id_matches():
    prospects = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
            "phone": "+442000000000",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "business_name": "Beta HVAC",
            "niche": "hvac",
            "metro": "Leeds",
            "phone": "+441130000000",
        },
    ]
    acquisitions = [
        {
            "prospect_id": prospects[1]["id"],
            "evidence": {
                "raw": {"external_lead_id": "legacy-beta"}
            },
        }
    ]
    crm = [
        {
            "lead_uid": prospects[0]["id"],
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
        },
        {
            "lead_uid": "legacy-beta",
            "business_name": "Beta HVAC",
            "niche": "hvac",
            "metro": "Leeds",
        },
    ]

    report = build_parity_report(
        prospects=prospects,
        acquisitions=acquisitions,
        crm_leads=crm,
        lane_leads=[],
    )

    assert report["matched_legacy_rows"] == 2
    assert report["unmatched_legacy_rows"] == 0
    assert report["crm_matches"][0]["method"] == "canonical_uuid"
    assert report["crm_matches"][1]["method"] == (
        "acquisition_external_id"
    )
    assert report["canonical_without_legacy"] == []


def test_unique_identity_is_diagnostic_fallback_only():
    prospect = {
        "id": "11111111-1111-1111-1111-111111111111",
        "business_name": "Acme   Ltd",
        "niche": "Roofing",
        "metro": "London",
    }
    crm = [{
        "lead_uid": "old-123",
        "business_name": " acme ltd ",
        "niche": "roofing",
        "metro": "london",
    }]

    report = build_parity_report(
        prospects=[prospect],
        acquisitions=[],
        crm_leads=crm,
        lane_leads=[],
    )

    match = report["crm_matches"][0]
    assert match["method"] == "identity_diagnostic"
    assert match["confidence"] == 0.70
    assert match["prospect_id"] == prospect["id"]


def test_ambiguous_identity_fails_closed_instead_of_guessing():
    prospects = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
        },
    ]
    lane = [{
        "prospect_id": "legacy-acme",
        "business_name": "Acme Ltd",
        "niche": "roofing",
        "metro": "London",
    }]

    report = build_parity_report(
        prospects=prospects,
        acquisitions=[],
        crm_leads=[],
        lane_leads=lane,
    )

    match = report["lane_matches"][0]
    assert match["method"] == "ambiguous"
    assert match["prospect_id"] is None
    assert match["reason"] == "identity_maps_to_multiple_prospects"
    assert report["ambiguous_identity_rows"] == 1


def test_field_mismatches_are_reported_not_reconciled():
    prospect_id = "11111111-1111-1111-1111-111111111111"
    report = build_parity_report(
        prospects=[{
            "id": prospect_id,
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
            "phone": "+442000000000",
        }],
        acquisitions=[],
        crm_leads=[{
            "lead_uid": prospect_id,
            "business_name": "Acme Limited",
            "niche": "roofing",
            "metro": "Manchester",
            "phone": "+442000000000",
        }],
        lane_leads=[],
    )

    match = report["crm_matches"][0]
    assert set(match["mismatches"]) == {
        "business_name",
        "metro",
    }
    assert report["field_mismatch_rows"] == 1


def test_canonical_without_legacy_is_explicit():
    prospect_id = "11111111-1111-1111-1111-111111111111"
    report = build_parity_report(
        prospects=[{
            "id": prospect_id,
            "business_name": "Acme Ltd",
            "niche": "roofing",
            "metro": "London",
        }],
        acquisitions=[],
        crm_leads=[],
        lane_leads=[],
    )

    assert report["canonical_without_legacy"] == [prospect_id]


def test_unknown_acquisition_reference_is_rejected():
    try:
        build_parity_report(
            prospects=[],
            acquisitions=[{
                "prospect_id": (
                    "11111111-1111-1111-1111-111111111111"
                ),
                "evidence": {},
            }],
            crm_leads=[],
            lane_leads=[],
        )
    except LeadParityError as exc:
        assert "unknown prospect" in str(exc)
    else:
        raise AssertionError("expected LeadParityError")


def test_fetch_inputs_uses_bounded_read_only_queries():
    calls = []

    def reader(path, params):
        calls.append((path, dict(params)))
        return []

    prospects, acquisitions = fetch_canonical_parity_inputs(
        reader,
        limit=250,
    )

    assert prospects == []
    assert acquisitions == []
    assert calls[0][0] == "/rest/v1/prospects"
    assert calls[1][0] == "/rest/v1/prospect_acquisitions"
    assert calls[0][1]["limit"] == "250"
    assert calls[1][1]["limit"] == "250"
