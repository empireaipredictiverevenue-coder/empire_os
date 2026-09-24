from urllib.parse import parse_qs, urlparse

from empire_os.legacy_permit_recovery import (
    build_recovery_observer,
    dedupe_legacy_lane_rows,
    fetch_legacy_permit_rows,
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
    assert record["current_identity_match_state"] == "UNKNOWN_NOT_CHECKED"
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
    assert params["limit"] == ["2500"]
    assert params["offset"] == ["7"]
