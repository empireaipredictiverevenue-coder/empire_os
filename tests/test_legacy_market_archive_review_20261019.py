"""No writes, PII exports, buyer promotion or prediction tuning from USB."""
import csv
import json
from pathlib import Path

import pytest

from empire_os.legacy_market_archive_review_20261019 import (
    review_metro_json, review_expected_value_csv,
)
from scripts.review_legacy_usb_market_archives_20261019 import main


def _metro(tmp_path: Path, companies) -> Path:
    target = tmp_path / "metro.json"
    target.write_text(json.dumps({
        "phase": 1, "summary": {"expected_revenue": 999999999},
        "metros": [{"metro": "Private Metro", "companies": companies}],
    }))
    return target


def _csv(tmp_path: Path, rows, *, headers=None) -> Path:
    target = tmp_path / "expected.csv"
    fields = headers or ["category", "service", "zipcode", "expected_value"]
    with target.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return target


def test_metro_duplicates_do_not_become_verified_opportunities(tmp_path):
    p = _metro(tmp_path, [
        {"name": "PRIVATE COMPANY", "website": "private-site.example",
         "email": "private@example.com", "confidence": 0.9},
        {"name": "PRIVATE COMPANY", "website": "private-site.example",
         "email": "private@example.com", "confidence": 0.9},
        {"name": "ANOTHER", "website": "another.example",
         "email": "private2@example.com", "confidence": 0.9},
    ])
    d = review_metro_json(p)
    counts = d["statistics"]
    assert counts["company_rows"] == 3
    assert counts["unique_names"] == 2
    assert counts["duplicate_name_rows"] == 1
    assert counts["distinct_confidence_values"] == 1
    assert counts["explicit_source_observation_rights_rows"] == 0
    assert d["source_ready_for_canonical_import"] is False
    assert d["model_calibration_authorized"] is False
    assert d["database_writes"] is False
    assert "PRIVATE" not in json.dumps(d)
    assert "example.com" not in json.dumps(d)


def test_recorded_source_does_not_bypass_second_authority(tmp_path):
    p = _metro(tmp_path, [
        {"name": "PRIVATE", "source_url": "https://private.example/source",
         "source_observed_at": "2026-10-18T17:00:00+00:00",
         "source_use_rights_verified": True}
    ])
    d = review_metro_json(p)
    assert d["statistics"]["explicit_source_observation_rights_rows"] == 1
    assert d["independent_source_rights_verified"] is False
    assert d["source_ready_for_canonical_import"] is False


def test_csv_duplicates_are_visible_without_exporting_zipcodes(tmp_path):
    p = _csv(tmp_path, [
        {"category": "Roofing", "service": "repair", "zipcode": "12345", "expected_value": "5.5"},
        {"category": "Roofing", "service": "repair", "zipcode": "12345", "expected_value": "6"},
        {"category": "Roofing", "service": "replace", "zipcode": "12345", "expected_value": "8"},
    ])
    d = review_expected_value_csv(p)
    assert d["statistics"]["data_rows"] == 3
    assert d["statistics"]["duplicate_dimension_key_rows"] == 1
    assert d["statistics"]["distinct_category_service_zip_keys"] == 2
    assert d["statistics"]["has_observed_outcome_column"] is False
    assert d["statistics"]["historical_expected_value_is_modelled_only"] is True
    assert d["legacy_forecasts_are_not_realised_revenue"] is True
    assert "12345" not in json.dumps(d)


@pytest.mark.parametrize("value", ["NaN", "-1", "Infinity", "not-a-number"])
def test_bad_expected_values_count_not_accepted(tmp_path, value):
    p = _csv(tmp_path, [{
        "category": "Roofing", "service": "repair",
        "zipcode": "12345", "expected_value": value,
    }])
    d = review_expected_value_csv(p)
    assert d["statistics"]["invalid_modelled_values"] == 1
    assert d["source_ready_for_canonical_import"] is False


def test_csv_no_source_even_with_large_projection(tmp_path):
    p = _csv(tmp_path, [{
        "category": "Roofing", "service": "repair",
        "zipcode": "12345", "expected_value": "1000000",
    }])
    d = review_expected_value_csv(p)
    assert d["statistics"]["rows_with_explicit_source_and_verified_outcome_evidence"] == 0
    assert d["statistics"]["has_verified_revenue_column"] is False
    assert d["outbound_authorized"] is False


def test_reject_symlink_to_sensitive_data(tmp_path):
    original = _metro(tmp_path, [{"name": "PRIVATE"}])
    alias = tmp_path / "alias.json"
    alias.symlink_to(original)
    with pytest.raises(ValueError):
        review_metro_json(alias)


def test_reject_csv_missing_required_columns(tmp_path):
    p = _csv(tmp_path, [{"category": "Roofing"}], headers=["category"])
    with pytest.raises(ValueError):
        review_expected_value_csv(p)


def test_reject_malformed_metro_and_no_path_exposure(tmp_path, capsys):
    path = tmp_path / "metro.json"
    path.write_text(json.dumps({"companies": [{"phone": "PRIVATE-0000"}]}))
    code = main(["--read-only", "--metro-json", str(path)])
    d = json.loads(capsys.readouterr().out)
    assert code == 2
    assert d["state"] == "HOLD_UNTRUSTED_OR_UNAVAILABLE_ARCHIVE"
    assert "PRIVATE" not in json.dumps(d)
    assert str(path) not in json.dumps(d)


def test_cli_combines_two_local_review_outputs(tmp_path, capsys):
    a = _metro(tmp_path, [{"name": "Private Ltd", "website": "private.example"}])
    b = _csv(tmp_path, [{
        "category": "Roofing", "service": "repair",
        "zipcode": "12345", "expected_value": "2.4",
    }])
    code = main(["--read-only", "--metro-json", str(a),
                 "--expected-value-csv", str(b)])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["reviews"]["metro"]["statistics"]["company_rows"] == 1
    assert report["reviews"]["expected_value"]["statistics"]["data_rows"] == 1
    assert report["outbound_authorized"] is False
    assert report["canonical_empiredb_writes"] is False
    assert report["buyer_or_subscriber_status_promoted"] is False
    assert "Private Ltd" not in json.dumps(report)
