from urllib.parse import parse_qs, urlparse

from empire_os.legacy_permit_recovery import (
    build_recovery_observer,
    dedupe_legacy_lane_rows,
    fetch_canonical_prospects_by_metro,
    fetch_legacy_permit_rows,
    match_canonical_identity,
    parse_legacy_lane_notes,
    revalidate_nyc_permits,
)


NYC_NOTE = (
    "name=Peykar Realty (Queens) email= phone=(718) 348-9398 "
    "metro=NYC state=NY details=NB.PL permit 401975190 "
    "issued 2026-08-16: . BBL 4092480052. "
    "Address: 84-90 127 STREET, Queens"
)


def _row(
    prospect_id="prospect_260818004225268804",
    *,
    notes=NYC_NOTE,
    created_at="2026-08-18T00:42:25+00:00",
    row_id=1,
    lane_id="lane-1",
):
    return {
        "id": row_id,
        "lane_id": lane_id,
        "prospect_id": prospect_id,
        "status": "pending",
        "omega_score": 75,
        "omega_tier": "gold",
        "notes": notes,
        "created_at": created_at,
        "buyer_id": None,
        "niche": "plumbing",
        "metro": "NYC",
    }


def test_parse_legacy_nyc_permit_identity():
    parsed = parse_legacy_lane_notes(NYC_NOTE)

    assert parsed["parsed"] is True
    assert parsed["business_name"] == "Peykar Realty"
    assert parsed["phone_digits"] == "7183489398"
    assert parsed["metro"] == "NYC"
    assert parsed["state"] == "NY"
    assert parsed["permit_number"] == "401975190"
    assert parsed["permit_issued_date"] == "2026-08-16"
    assert parsed["bbl"] == "4092480052"
    assert parsed["address"] == "84-90 127 STREET, Queens"
    assert parsed["source_system"] == "nyc_dob_permits"
    assert parsed["legacy_name_role"] == "property_owner"
    assert parsed["legacy_phone_role"] == "permittee_contact"
    assert parsed["identity_recoverable"] is True
    assert parsed["identity_fingerprint"]


def test_placeholder_identity_is_not_recoverable():
    parsed = parse_legacy_lane_notes(
        "name=N/A (Brooklyn) email= phone=(718) 321-2500 "
        "metro=NYC state=NY details=A2.PL permit 310301839 "
        "issued 2026-08-16: . BBL 3008910037. "
        "Address: 300 20TH STREET, Brooklyn"
    )

    assert parsed["business_name"] == "N/A"
    assert parsed["permit_evidence_present"] is True
    assert parsed["identity_recoverable"] is False
    assert parsed["routing_only"] is True


def test_dedupe_collapses_lane_rows_and_keeps_latest():
    old = _row(
        created_at="2026-08-18T00:00:00+00:00",
        row_id=1,
        lane_id="lane-old",
    )
    new = _row(
        created_at="2026-08-19T00:00:00+00:00",
        row_id=2,
        lane_id="lane-new",
    )

    result = dedupe_legacy_lane_rows([old, new])

    assert len(result) == 1
    assert result[0]["id"] == 2
    assert result[0]["legacy_lane_row_count"] == 2
    assert result[0]["legacy_lane_ids"] == ["lane-new", "lane-old"]
    assert result[0]["dedupe_status"] == "DUPLICATE_LANE_ROWS_COLLAPSED"


def test_verified_current_permit_is_reuse_but_never_promoted():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["Peykar Realty"],
            }
        },
    )

    assert payload["processed_count"] == 1
    assert payload["classification_counts"] == {"REUSE": 1}
    assert payload["recovery_state_counts"] == {"VERIFIED_CURRENT": 1}

    record = payload["records"][0]
    assert record["recovery_classification"] == "REUSE"
    assert record["recovery_state"] == "VERIFIED_CURRENT"
    assert record["historical_omega"]["historical_only"] is True
    assert record["historical_omega"]["current_truth"] is False
    assert record["source_owner_identity_state"] == "MATCHED"
    assert record["current_identity_match_state"] == "NO_MATCH"
    assert record["canonical_prospect_id"] is None
    assert record["canonical_promotion_performed"] is False
    assert record["commercial_ready"] is False
    assert record["outreach_authorized"] is False
    assert payload["database_write_performed"] is False
    assert payload["outbound_sent"] is False
    assert payload["actual_revenue"] is False
    assert payload["execution_authority"] == "none"


def test_not_found_permit_is_archived_not_promoted():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "NOT_FOUND",
                "validation_reason": "no_current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "NOT_CONFIRMED",
            }
        },
    )

    record = payload["records"][0]
    assert record["recovery_classification"] == "ARCHIVE"
    assert record["recovery_state"] == "REVALIDATION_FAILED"
    assert record["canonical_promotion_performed"] is False


def test_unsupported_source_stays_revalidation_pending():
    chi_note = (
        "name=Example Property LLC email= phone=3125550100 "
        "metro=CHI state=IL details=SOLAR WORK - permit #B200481792 "
        "issued 2026-08-19. Address: 123 W TEST ST, Chicago"
    )
    row = _row(
        prospect_id="prospect_chi_1",
        notes=chi_note,
    )
    row["metro"] = "CHI"
    row["niche"] = "solar"

    payload = build_recovery_observer([row], nyc_validation={})

    record = payload["records"][0]
    assert record["recovered_fields"]["source_system"] == (
        "chicago_permits_legacy"
    )
    assert record["validation"]["validation_state"] == (
        "REVALIDATION_PENDING"
    )
    assert record["recovery_classification"] == "MODERNIZE"
    assert record["recovery_state"] == "REVALIDATION_PENDING"
    assert record["canonical_promotion_performed"] is False


def test_revalidate_nyc_permits_batches_and_matches(monkeypatch):
    seen = []

    class Response:
        status_code = 200

        def json(self):
            return [{
                "job__": "401975190",
                "dobrundate": "2026-08-16T00:00:00.000",
                "permit_status": "ISSUED",
                "owner_s_business_name": "Peykar Realty",
                "owner_s_first_name": "",
                "owner_s_last_name": "",
                "permittee_s_business_name": "Pipe Co",
                "permittee_s_first_name": "",
                "permittee_s_last_name": "",
                "permittee_s_phone__": "7183489398",
                "permittee_s_license_type": "MP",
                "permittee_s_license__": "12345",
                "house__": "84-90",
                "street_name": "127 STREET",
                "borough": "QUEENS",
            }]

    def fake_get(url, params, timeout):
        seen.append((url, params, timeout))
        return Response()

    monkeypatch.setattr(
        "empire_os.legacy_permit_recovery.requests.get",
        fake_get,
    )

    result = revalidate_nyc_permits(
        ["401975190", "999999999"],
        timeout=3.0,
    )

    assert len(seen) == 1
    assert "job__ in(" in seen[0][1]["$where"]
    assert result["401975190"]["validation_state"] == "VERIFIED_CURRENT"
    assert result["401975190"]["source_owner_names"] == ["Peykar Realty"]
    assert result["401975190"]["source_permittees"][0]["business_name"] == (
        "Pipe Co"
    )
    assert result["401975190"]["source_permittees"][0]["phone"] == (
        "7183489398"
    )
    assert result["999999999"]["validation_state"] == "NOT_FOUND"


def test_fetch_is_read_only_and_bounded(monkeypatch):
    calls = []

    def fake_request(method, path):
        calls.append((method, path))
        return [_row()]

    monkeypatch.setattr(
        "empire_os.legacy_permit_recovery.request_json",
        fake_request,
    )

    rows, next_offset, scan_limit = fetch_legacy_permit_rows(
        batch_size=9999,
        offset=7,
    )

    assert len(rows) == 1
    assert next_offset == 0
    assert scan_limit == 2500
    assert calls[0][0] == "GET"
    parsed = urlparse(calls[0][1])
    params = parse_qs(parsed.query)
    assert params["prospect_id"] == ["like.prospect_*"]
    assert params["notes"] == ["ilike.*permit*"]
    assert params["limit"] == ["500"]
    assert params["offset"] == ["7"]
    assert params["order"] == ["prospect_id.asc,created_at.asc,id.asc"]


def test_verified_current_exact_owner_name_becomes_merge_candidate():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["Peykar Realty"],
            }
        },
        canonical_prospects_by_metro={
            "nyc": {
                "rows": [{
                    "id": "canonical-1",
                    "business_name": "Peykar Realty",
                    "phone": "7183489398",
                    "metro": "nyc",
                }],
                "rows_scanned": 1,
                "truncated": False,
            }
        },
    )

    record = payload["records"][0]
    assert record["current_identity_match_state"] == "MATCHED"
    assert record["canonical_match_method"] == "exact_name_metro"
    assert record["canonical_prospect_id"] == "canonical-1"
    assert record["recovery_classification"] == "MERGE"
    assert record["recovery_state"] == "VERIFIED_CURRENT"
    assert record["canonical_promotion_performed"] is False
    assert payload["classification_counts"] == {"MERGE": 1}


def test_verified_current_ambiguous_identity_requires_review():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["Peykar Realty"],
            }
        },
        canonical_prospects_by_metro={
            "nyc": {
                "rows": [
                    {
                        "id": "canonical-1",
                        "business_name": "Peykar Realty",
                        "phone": "1111111111",
                        "metro": "nyc",
                    },
                    {
                        "id": "canonical-2",
                        "business_name": "Peykar Realty",
                        "phone": "2222222222",
                        "metro": "nyc",
                    },
                ],
                "rows_scanned": 2,
                "truncated": False,
            }
        },
    )

    record = payload["records"][0]
    assert record["current_identity_match_state"] == "AMBIGUOUS"
    assert record["canonical_match_reason"] == (
        "multiple_exact_name_metro_matches"
    )
    assert record["canonical_prospect_id"] is None
    assert record["recovery_classification"] == "MODERNIZE"
    assert record["recovery_state"] == "IDENTITY_REVIEW_REQUIRED"
    assert record["canonical_promotion_performed"] is False


def test_canonical_lookup_reuses_existing_match_contract():
    parsed = parse_legacy_lane_notes(NYC_NOTE)
    result = match_canonical_identity(
        parsed,
        {
            "nyc": {
                "rows": [{
                    "id": "canonical-name",
                    "business_name": "Peykar Realty",
                    "phone": "",
                    "metro": "NYC",
                }],
                "rows_scanned": 1,
                "truncated": False,
            }
        },
    )

    assert result["match_state"] == "MATCHED"
    assert result["match_method"] == "exact_name_metro"
    assert result["canonical_prospect_id"] == "canonical-name"


def test_canonical_lookup_is_read_only_and_bounded(monkeypatch):
    calls = []

    def fake_request(method, path):
        calls.append((method, path))
        if "offset=0" in path:
            return [{
                "id": "canonical-1",
                "business_name": "Peykar Realty",
                "phone": "7183489398",
                "metro": "nyc",
            }]
        return []

    monkeypatch.setattr(
        "empire_os.legacy_permit_recovery.request_json",
        fake_request,
    )

    result = fetch_canonical_prospects_by_metro(
        ["NYC"],
        page_size=10,
        max_rows_per_metro=100,
    )

    assert result["nyc"]["rows_scanned"] == 1
    assert result["nyc"]["truncated"] is False
    assert calls
    assert all(method == "GET" for method, _ in calls)
    assert "/rest/v1/prospects?" in calls[0][1]


def test_permittee_phone_does_not_merge_property_owner():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["Peykar Realty"],
            }
        },
        canonical_prospects_by_metro={
            "nyc": {
                "rows": [{
                    "id": "canonical-shared-phone",
                    "business_name": "Regional Scaffold & Hoisting",
                    "phone": "7183489398",
                    "metro": "nyc",
                }],
                "rows_scanned": 1,
                "truncated": False,
            }
        },
    )

    record = payload["records"][0]
    assert record["recovered_fields"]["legacy_name_role"] == (
        "property_owner"
    )
    assert record["recovered_fields"]["legacy_phone_role"] == (
        "permittee_contact"
    )
    assert record["current_identity_match_state"] == "NO_MATCH"
    assert record["canonical_match_reason"] == "no_strong_identity_match"
    assert record["canonical_prospect_id"] is None
    assert record["source_owner_identity_state"] == "MATCHED"
    assert record["recovery_classification"] == "REUSE"
    assert record["recovery_state"] == "VERIFIED_CURRENT"
    assert record["canonical_promotion_performed"] is False


def test_current_permit_owner_mismatch_requires_identity_review():
    payload = build_recovery_observer(
        [_row()],
        nyc_validation={
            "401975190": {
                "validation_state": "VERIFIED_CURRENT",
                "validation_reason": "current_public_source_match",
                "source_system": "nyc_dob_permits",
                "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                "source_owner_names": ["Different Owner LLC"],
            }
        },
    )

    record = payload["records"][0]
    assert record["source_owner_identity_state"] == "MISMATCH"
    assert record["recovery_classification"] == "MODERNIZE"
    assert record["recovery_state"] == "IDENTITY_REVIEW_REQUIRED"
    assert record["canonical_promotion_performed"] is False


def test_nyc_owner_fingerprint_does_not_depend_on_permittee_phone():
    first = parse_legacy_lane_notes(NYC_NOTE)
    second = parse_legacy_lane_notes(
        NYC_NOTE.replace("(718) 348-9398", "(212) 555-9999")
    )

    assert first["legacy_phone_role"] == "permittee_contact"
    assert second["legacy_phone_role"] == "permittee_contact"
    assert first["identity_fingerprint"] == second["identity_fingerprint"]


def test_generic_owner_labels_are_not_recoverable():
    for name in ("OWNER", "N.A", "N/A", "245"):
        parsed = parse_legacy_lane_notes(
            f"name={name} email= phone=(718) 555-0100 "
            "metro=NYC state=NY details=A2.PL permit 401975190 "
            "issued 2026-08-16: . BBL 4092480052. "
            "Address: 84-90 127 STREET, Queens"
        )
        assert parsed["identity_recoverable"] is False
        assert parsed["routing_only"] is True
