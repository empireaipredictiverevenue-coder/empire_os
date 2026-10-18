"""Official-source sweep, licence/auth guardrails and two real-source parsers."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from empire_os.public_source_sweep import review_public_source_sweep
from empire_os.ea_flood_source_observer import (
    MAX_RESPONSE_BYTES, normalize_ea_flood_warnings, observe_ea_flood_warnings,
    SourceObservationUnavailable,
)
from empire_os.uk_public_tender_observer import (
    MAX_BYTES, normalize_uk_tender_releases, observe_uk_public_tenders,
    PublicTenderSourceUnavailable,
)

NOW = datetime(2026, 10, 18, 21, 40, tzinfo=timezone.utc)


def flood():
    return {
        "meta": {
            "publisher": "Environment Agency",
            "licence": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        },
        "items": [
            {
                "@id": "http://environment.data.gov.uk/flood-monitoring/id/floods/999001",
                "floodAreaID": "uk01FW",
                "severityLevel": 2,
                "timeMessageChanged": "2026-10-18T19:30:00",
                "description": "PRIVATE HOUSEHOLD NAME AND ADDRESS",
                "message": "private-public-text",
            },
        ],
    }


def tender():
    return {
        "publisher": {"name": "Cabinet Office"},
        "license": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "releases": [
            {
                "ocid": "ocds-h6vhtk-a1b2c3",
                "id": "012345-2026-release1",
                "tag": ["tender"],
                "buyer": {"name": "PRIVATE_BUYER_CONTACT", "email": "never@exported.com"},
                "tender": {
                    "title": "Solar installation PRIVATE PERSON",
                    "description": "PRIVATE_DESCRIPTION_SECRET",
                    "status": "active",
                    "classification": {"id": "09332000"},
                    "items": [{"classification": {"id": "45261215"}}],
                    "tenderPeriod": {"endDate": "2026-11-14T18:00:00Z"},
                },
            },
            {
                "ocid": "ocds-h6vhtk-abc123",
                "id": "012346-2026-release2",
                "tag": ["tender"],
                "tender": {
                    "status": "complete",
                    "classification": {"id": "85130000"},
                },
            },
        ],
    }


def test_deep_sweep_categorizes_and_prioritizes_without_enabling_sources():
    report = review_public_source_sweep(as_of=NOW)
    assert report["schema_version"] == "empire.public_source_sweep.v1"
    assert report["source_count"] >= 18
    assert report["by_readiness"]["API_KEY_REQUIRED"] >= 2
    assert report["by_readiness"]["REUSE_EXISTING"] >= 4
    assert report["by_readiness"]["BLOCKED_COMMERCIAL_FREE_TIER"] >= 1
    assert report["by_readiness"]["NO_ACTIVE_RECORDS"] >= 1
    assert report["paid_api_invoked"] is False
    assert report["source_polling_started"] is False
    assert report["execution_authority"] == "none"
    source = {row["source_key"]: row for row in report["sources"]}
    assert source["open_meteo_free_tier"]["readiness"] == "BLOCKED_COMMERCIAL_FREE_TIER"
    assert source["uk_epc"]["readiness"] == "LIMITED_SOURCE_RIGHTS"
    assert source["uk_companies_house"]["readiness"] == "API_KEY_REQUIRED"
    assert source["uk_planning_application_api"]["readiness"] == "NO_ACTIVE_RECORDS"
    assert source["us_nws_alerts"]["readiness"] == "REUSE_EXISTING"
    assert source["us_nyc_dobnow"]["readiness"] == "REUSE_EXISTING"
    assert all(row["active_ingestion_enabled_by_catalogue"] is False for row in source.values())
    assert list(report["by_readiness"]) == sorted(report["by_readiness"])
    assert report == review_public_source_sweep(as_of=NOW)


def test_flood_source_converts_only_public_observations_not_damage():
    report = normalize_ea_flood_warnings(flood(), retrieved_at=NOW)
    assert report["status"] == "SOURCE_SAMPLE_OBSERVED"
    assert report["source_records_in_sample"] == 1
    assert report["warning_severity_counts_in_sample"] == {"2": 1}
    assert report["source_observations"][0]["source_evidence"]["source_truth"] == "OBSERVED_SOURCE_RECORD"
    assert report["source_observations"][0]["source_evidence"]["raw_evidence_hash"]
    assert report["source_global_total_known"] is False
    assert report["physical_event_truth"] == "UNKNOWN"
    assert report["geographic_property_owner_or_damage_proven"] is False
    assert report["canonical_signal_inbox_mutated"] is False
    assert "PRIVATE HOUSEHOLD" not in json.dumps(report)
    assert "private-public-text" not in json.dumps(report)


def test_flood_no_events_does_not_claim_no_hazards():
    packet = flood()
    packet["items"] = []
    out = normalize_ea_flood_warnings(packet, retrieved_at=NOW)
    assert out["status"] == "ZERO_WARNINGS_IN_SOURCE_SAMPLE"
    assert out["source_global_total_known"] is False
    assert out["source_observations"] == []


@pytest.mark.parametrize("mutate", [
    lambda d: d["meta"].update(publisher="Fake Agency"),
    lambda d: d["meta"].update(licence="https://invalid.example/test"),
    lambda d: d["items"][0].update(severityLevel=99),
    lambda d: d["items"][0].update(floodAreaID="../../bad"),
    lambda d: d["items"][0].update(**{"@id": "https://evil.example/foo"}),
    lambda d: d["items"].append(deepcopy(d["items"][0])),
])
def test_flood_rejects_fake_sources_and_duplicates(mutate):
    item = flood()
    mutate(item)
    with pytest.raises(ValueError):
        normalize_ea_flood_warnings(item, retrieved_at=NOW)


def test_bounded_flood_fetch_is_one_mock_call_and_never_writes():
    calls = []
    def fetch():
        calls.append(1)
        return json.dumps(flood()).encode()
    report = observe_ea_flood_warnings(as_of=NOW, fetcher=fetch)
    assert calls == [1]
    assert report["source_downloaded_by_review"] is True
    assert report["outbound_sent"] is False
    assert report["payments_moved"] is False


def test_flood_oversize_is_held():
    with pytest.raises(SourceObservationUnavailable):
        observe_ea_flood_warnings(
            as_of=NOW, fetcher=lambda: b"A" * (MAX_RESPONSE_BYTES + 1),
        )


def test_tender_cpv_mapping_and_active_deadline_are_only_scenario_signals():
    result = normalize_uk_tender_releases(tender(), as_of=NOW)
    assert result["status"] == "PUBLIC_TENDER_SAMPLE_OBSERVED"
    assert result["record_count_in_bounded_page"] == 2
    assert result["vertical_matches_in_page"] == {"dental": 1, "solar": 1}
    assert result["tender_status_counts_in_page"] == {"active": 1, "complete": 1}
    assert result["source_observations"][0]["buyer_acceptance_or_payment_verified"] is False
    assert any(row["future_submissions_deadline_evidenced"]
               for row in result["source_observations"])
    assert result["actual_contract_or_revenue_proven"] is False
    assert result["customer_or_supplier_contacts_returned"] is False
    for forbidden in ("PRIVATE_BUYER_CONTACT", "PRIVATE_DESCRIPTION_SECRET",
                      "PRIVATE PERSON", "never@exported.com"):
        assert forbidden not in json.dumps(result)


@pytest.mark.parametrize("mutate", [
    lambda d: d["publisher"].update(name="Unauthorized"),
    lambda d: d.update(license="https://another.license"),
    lambda d: d["releases"][0].update(tag=["award"]),
    lambda d: d["releases"][0].update(ocid="http://example.com"),
    lambda d: d["releases"].append(deepcopy(d["releases"][0])),
])
def test_tender_rejects_forged_and_duplicated_release(mutate):
    record = tender()
    mutate(record)
    with pytest.raises(ValueError):
        normalize_uk_tender_releases(record, as_of=NOW)


def test_tender_one_bounded_fetch_does_not_create_crm_buyer():
    calls = []
    def fetch():
        calls.append(1)
        return json.dumps(tender()).encode()
    result = observe_uk_public_tenders(as_of=NOW, fetcher=fetch)
    assert calls == [1]
    assert result["existing_opportunity_or_crm_created"] is False
    assert result["outreach_or_bid_authorized"] is False
    assert result["worker_dispatched"] is False


def test_tender_response_oversize_rejected():
    with pytest.raises(PublicTenderSourceUnavailable):
        observe_uk_public_tenders(as_of=NOW,
            fetcher=lambda: b"x" * (MAX_BYTES + 1))


def test_source_deep_sweep_uses_existing_department_queue_without_new_workers(tmp_path):
    from empire_os.public_source_sweep import enqueue_deep_source_reviews
    report = review_public_source_sweep(as_of=NOW)
    result = enqueue_deep_source_reviews(
        str(tmp_path), report, allow_noncanonical_test=True,
    )
    assert result["new_review_tasks"] == 2
    assert result["duplicate_review_tasks"] == 0
    assert result["paid_provider_invoked"] is False
    assert result["external_source_polling_started"] is False
    assert result["outbound_sent"] is False
    repeated = enqueue_deep_source_reviews(
        str(tmp_path), report, allow_noncanonical_test=True,
    )
    assert repeated["new_review_tasks"] == 0
    assert repeated["duplicate_review_tasks"] == 2
    task_files = sorted((tmp_path/"runtime/departments/work/ready").glob("*.json"))
    assert len(task_files) == 2
    for f in task_files:
        task = json.loads(f.read_text())
        assert task["authority"] == "observe"
        assert task["intelligence_request"]["budget"] == {
            "requested_model_tokens": 0,
            "requested_external_cost_cents": 0,
        }
        assert task["intelligence_request"]["official_source_deep_sweep"]["public_metadata_only"] is True
        assert task["target_component"] == "existing_source_intelligence_and_sensor_mesh"
        assert "@" not in json.dumps(task)


@pytest.mark.parametrize("changed", [
    lambda d: d["sources"][0].update(readiness="REUSE_EXISTING"),
    lambda d: d.update(metadata_fingerprint="f"*64),
    lambda d: d.update(source_polling_started=True),
])
def test_source_deep_sweep_rejects_catalogue_tampering(tmp_path, changed):
    from empire_os.public_source_sweep import enqueue_deep_source_reviews
    catalogue = deepcopy(review_public_source_sweep(as_of=NOW))
    changed(catalogue)
    with pytest.raises(ValueError, match="untrusted"):
        enqueue_deep_source_reviews(
            str(tmp_path), catalogue, allow_noncanonical_test=True,
        )
    assert not (tmp_path/"runtime/departments/work").exists()


def test_noncanonical_source_queue_scope_must_be_explicit(tmp_path):
    from empire_os.public_source_sweep import enqueue_deep_source_reviews
    with pytest.raises(PermissionError):
        enqueue_deep_source_reviews(
            str(tmp_path), review_public_source_sweep(as_of=NOW)
        )
