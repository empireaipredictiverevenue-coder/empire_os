"""Source records are synthetic *tests only*, never production inputs."""
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.data_exchange_construction import build_construction_preview

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


def signal(**changes):
    row = {
        "record_id": "123456",
        "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land",
        "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": "https://www.planning.data.gov.uk/entity/123456",
        "source_observed_at": "2026-10-14T09:00:00+00:00",
    }
    row.update(changes)
    return row


def reviewed(**changes):
    row = {
        "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land",
        "licence_id": "OGL-3.0",
        "attribution": "Contains public sector information licensed under the Open Government Licence v3.0",
        "reviewed_by": "human reviewer",
        "reviewed_at": "2026-10-14T08:00:00Z",
        "review_status": "approved",
        "derived_product_use_cleared": True,
        "third_party_rights_cleared": True,
        "personal_data_excluded": True,
    }
    row.update(changes)
    return row


def preview(records, rights=None):
    return build_construction_preview(
        records, rights_review=rights, observed_at=NOW
    )


def test_rights_absent_blocks_commercial_even_for_valid_record():
    result = preview([signal()])
    assert result["dataset_record_count"] == 1
    assert result["assessment_status"] == "HOLD"
    assert result["rights_holds"] == ["RIGHTS_REVIEW_MISSING"]
    assert result["data_resale_authorized"] is False
    assert result["customer_delivery_enabled"] is False


def test_review_cannot_grant_automatic_distribution_or_payment():
    result = preview([signal()], reviewed())
    assert result["rights_review_eligible"] is True
    assert result["assessment_status"] == "RIGHTS_REVIEW_PASSED_INTERNAL_ONLY"
    assert result["source_claim_verification"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert result["execution_authority"] == "NONE"
    assert result["data_resale_authorized"] is False
    assert result["customer_delivery_enabled"] is False
    assert result["outbound_enabled"] is False
    assert result["payment_execution"] is False
    assert result["actual_revenue"] is False


@pytest.mark.parametrize("changes,expected", [
    ({"source_id": "gb_recc_solar"}, "RIGHTS_REVIEW_SCOPE_MISMATCH"),
    ({"dataset_id": "another"}, "RIGHTS_REVIEW_SCOPE_MISMATCH"),
    ({"review_status": "draft"}, "RIGHTS_REVIEW_NOT_APPROVED"),
    ({"licence_id": "unknown"}, "LICENCE_UNVERIFIED"),
    ({"derived_product_use_cleared": False}, "RIGHTS_RESTRICTION_UNRESOLVED"),
    ({"personal_data_excluded": False}, "RIGHTS_RESTRICTION_UNRESOLVED"),
    ({"third_party_rights_cleared": False}, "RIGHTS_RESTRICTION_UNRESOLVED"),
    ({"reviewed_at": "2025-01-01T00:00:00Z"}, "RIGHTS_REVIEW_STALE"),
    ({"reviewed_at": "2030-01-01T00:00:00Z"}, "RIGHTS_REVIEW_DATE_INVALID"),
])
def test_rights_gates_fail_closed(changes, expected):
    result = preview([signal()], reviewed(**changes))
    assert result["rights_review_eligible"] is False
    assert result["rights_holds"] == [expected]


@pytest.mark.parametrize("changes,reason", [
    ({"source_id": "permits_nyc"}, "OUT_OF_PILOT_SCOPE"),
    ({"region": "south_east_england"}, "OUT_OF_PILOT_SCOPE"),
    ({"dataset_id": "planning-application"}, "OUT_OF_PILOT_SCOPE"),
    ({"record_type": "planning_application"}, "OUT_OF_PILOT_SCOPE"),
    ({"source_url": "https://example.com/entity/123456"}, "SOURCE_EVIDENCE_MISSING"),
    ({"source_url": "http://www.planning.data.gov.uk/entity/123456"}, "SOURCE_EVIDENCE_MISSING"),
    ({"source_url": "https://www.planning.data.gov.uk.evil.com/entity/123456"}, "SOURCE_EVIDENCE_MISSING"),
    ({"source_url": "https://www.planning.data.gov.uk/"}, "SOURCE_EVIDENCE_MISSING"),
    ({"source_url": "https://www.planning.data.gov.uk/entity/654321"}, "SOURCE_EVIDENCE_MISSING"),
    ({"source_observed_at": "2025-01-01T00:00:00Z"}, "OBSERVATION_STALE"),
    ({"source_observed_at": "2030-01-01T00:00:00Z"}, "OBSERVATION_INVALID"),
    ({"source_observed_at": "2026-10-14T09:00:00"}, "OBSERVATION_INVALID"),
    ({"contact_email": "person@example.com"}, "UNREVIEWED_FIELDS"),
    ({"predicted_buyer_probability": 0.95}, "UNREVIEWED_FIELDS"),
])
def test_rejects_unverifiable_or_out_of_scope_rows(changes, reason):
    result = preview([signal(**changes)], reviewed())
    assert result["records"] == []
    assert result["rejected_counts"] == {reason: 1}
    assert result["assessment_status"] == "HOLD"


def test_dedupes_identical_verified_observations():
    result = preview([signal(), signal()], reviewed())
    assert len(result["records"]) == 1


def test_conflicting_id_does_not_select_arbitrary_record():
    different = signal(source_observed_at="2026-10-13T09:00:00Z")
    result = preview([signal(), different], reviewed())
    assert result["records"] == []
    assert result["rejected_counts"] == {"CONFLICTING_RECORD_ID": 1}


def test_empty_input_remains_unknown_not_launch_ready():
    result = preview([], reviewed())
    assert result["dataset_record_count"] == 0
    assert result["assessment_status"] == "HOLD"


def test_bounded_size_and_timezone():
    with pytest.raises(ValueError, match="bounded"):
        preview([signal()] * 1001)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_construction_preview([], observed_at=datetime(2026, 10, 14))


def test_bounded_official_fetch_produces_only_public_source_identity():
    from empire_os.data_exchange_construction import (
        normalise_official_brownfield_entities,
    )

    seen_urls = []

    def official_fetch(url):
        seen_urls.append(url)
        return {
            "entity": 1739547,
            "dataset": "brownfield-land",
            "quality": "authoritative",
            "organisation-entity": 207,
            "site-address": "DO NOT DISCLOSE ADDRESS",
            "notes": "DO NOT DISCLOSE FREE-TEXT NOTES",
            "planning-permission-status": "non-permissioned",
        }

    rows = normalise_official_brownfield_entities(
        [1739547], fetch_json=official_fetch, observed_at=NOW
    )
    assert seen_urls == [
        "https://www.planning.data.gov.uk/entity/1739547.json"
    ]
    assert len(rows) == 1
    assert set(rows[0]) == {
        "record_id", "source_id", "dataset_id", "region",
        "record_type", "source_url", "source_observed_at",
        "planning_permission_status", "site_area_hectares", "source_entry_date",
    }
    assert "DO NOT DISCLOSE" not in str(rows)
    assert preview(rows)["dataset_record_count"] == 1


@pytest.mark.parametrize("response", [
    {"entity": 5, "dataset": "brownfield-land", "quality": "authoritative", "organisation-entity": 207},
    {"entity": 1739547, "dataset": "planning-application", "quality": "authoritative", "organisation-entity": 207},
    {"entity": 1739547, "dataset": "brownfield-land", "quality": "uncertain", "organisation-entity": 207},
    {"entity": 1739547, "dataset": "brownfield-land", "quality": "authoritative", "organisation-entity": 1234},
    {"error": "none"},
])
def test_live_fetch_rejects_mismatched_source(response):
    from empire_os.data_exchange_construction import (
        normalise_official_brownfield_entities,
    )

    with pytest.raises(ValueError, match="mismatch"):
        normalise_official_brownfield_entities(
            [1739547], fetch_json=lambda _: response, observed_at=NOW,
        )


def test_duplicate_conflicting_records_remain_quarantined():
    result = preview(
        [signal(), signal(source_observed_at="2026-10-13T09:00:00Z"), signal()],
        reviewed(),
    )
    assert result["records"] == []
    assert result["rejected_counts"]["CONFLICTING_RECORD_ID"] == 2


def test_malformed_port_and_path_escape_fail_closed():
    for bad in (
        "https://www.planning.data.gov.uk:invalid/entity/123456",
        "https://www.planning.data.gov.uk/entity/123456/../123456",
        "https://user:pass@www.planning.data.gov.uk/entity/123456",
    ):
        result = preview([signal(source_url=bad)])
        assert result["dataset_record_count"] == 0


def test_readonly_input_cli_load_has_bounded_schema(tmp_path):
    import json
    from scripts.preview_construction_data_exchange import load_input

    path = tmp_path / "input.json"
    path.write_text(json.dumps({"records": [signal()]}))
    assert len(load_input(path)["records"]) == 1
    path.write_text(json.dumps({"records": [], "secret": "bad"}))
    with pytest.raises(ValueError, match="only records"):
        load_input(path)


def test_live_probe_rejects_unapproved_host():
    from scripts.probe_construction_official_entities import fetch_official_json

    with pytest.raises(ValueError, match="non-official"):
        fetch_official_json("https://attacker.example/entity/1739547.json")


@pytest.mark.parametrize("extra,reason", [
    ({"planning_permission_status": "application-will-win"}, "UNRECOGNISED_PLANNING_STATUS"),
    ({"planning_permission_status": ["permissioned"]}, "UNRECOGNISED_PLANNING_STATUS"),
    ({"site_area_hectares": "-1"}, "INVALID_SITE_AREA"),
    ({"site_area_hectares": "NaN"}, "INVALID_SITE_AREA"),
    ({"site_area_hectares": "Infinity"}, "INVALID_SITE_AREA"),
    ({"site_area_hectares": True}, "INVALID_SITE_AREA"),
    ({"site_area_hectares": "100001"}, "INVALID_SITE_AREA"),
])
def test_government_fields_fail_closed(extra, reason):
    result = preview([signal(**extra)])
    assert result["dataset_record_count"] == 0
    assert result["rejected_counts"] == {reason: 1}


def test_government_status_and_area_are_observations_not_predictions():
    result = preview([signal(
        planning_permission_status="pending-decision",
        site_area_hectares="0.532491",
    )])
    assert result["dataset_record_count"] == 1
    row = result["records"][0]
    assert row["planning_permission_status"] == "pending-decision"
    assert row["site_area_hectares"] == "0.532491"
    assert row["signal_class"] == "development_context_not_buyer_intent"
    assert result["customer_delivery_enabled"] is False


@pytest.mark.parametrize("source_entry_date", [
    "2026-99-99", "2030-01-01", "14/10/2026",
    "2026-01-01T00:00:00Z", 20261014, True,
])
def test_source_entry_date_must_be_historically_valid(source_entry_date):
    result = preview([signal(source_entry_date=source_entry_date)])
    assert result["dataset_record_count"] == 0
    assert result["rejected_counts"] == {"INVALID_SOURCE_ENTRY_DATE": 1}


def test_historic_entry_date_is_not_the_time_we_observed_project():
    result = preview([signal(source_entry_date="2018-05-22")])
    assert result["dataset_record_count"] == 1
    assert result["records"][0]["source_entry_date"] == "2018-05-22"
    assert result["records"][0]["source_observed_at"] == "2026-10-14T09:00:00+00:00"
