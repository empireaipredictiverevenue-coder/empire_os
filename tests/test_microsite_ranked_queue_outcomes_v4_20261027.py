"""V4 queue, original calibration and page measurement contract."""
from copy import deepcopy
from hashlib import sha256
from datetime import date, timedelta
import json
from pathlib import Path
import runpy

import pytest

from empire_os.microsite_ranked_production_queue_v4 import build_ranked_microsite_queue
from empire_os.microsite_calibration_bridge_v4 import review_historical_model_calibration
from empire_os.microsite_page_outcomes_v4 import (
    original_site_search_baseline, build_microsite_outcome_register,
    read_original_weekly_search_report,
)
from empire_os.microsite_first_party_gsc_bridge import connect_factory_to_gsc
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from datetime import datetime, timezone

NOW = datetime(2026, 10, 27, 13, 37, tzinfo=timezone.utc)


def inputs():
    spec = runpy.run_path(str(Path(__file__).with_name(
        "test_predictive_microsite_factory_20261026.py")))["candidate"]()
    second = deepcopy(spec)
    second["geography"] = {"market_id": "US-TX", "kind": "metro",
                            "area": "Dallas, TX", "evidence_refs": ["geo-registry:US-TX"]}
    second["keyword_opportunity"]["keyword"] = "Dallas roof replacement research"
    second["keyword_opportunity"]["territory_key"] = "US-TX"
    second["headline"] = "Dallas roof research: source-driven decisions"
    second["local_facts"][0]["statement"] = "The existing geo registry lists Dallas as a research market."
    second["local_facts"][0]["source_ref"] = "empire_os/geo_registry.py:US-TX"
    return [spec, second]


def queue(specs=None):
    specs = specs or inputs()
    commercial = build_microsite_commercial_review(specs, now=NOW)
    return build_ranked_microsite_queue(specs, commercial=commercial)


def historical_case(n=1):
    last = date(2026, 10, 10) + timedelta(days=n)
    observations = [
        {"observed_date": (last - timedelta(days=9-i)).isoformat(),
         "value": float(i+4+n), "source": f"owner:query-series:{n}:{i}"}
        for i in range(10)]
    from empire_os.predictive_materializer import materialize_daily_actuals
    materialization = materialize_daily_actuals(
        metric="observed_search_query_impressions", rows=observations,
        value_field="value", date_field="observed_date", horizon_days=7)
    frozen = sha256(json.dumps(
        materialization.as_dict(), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "issued_at": last.isoformat() + "T18:00:00Z",
        "original_immutable_forecast_sha256": frozen,
        "source_owner": "empire_os.predictive_registry",
        "model_name": "observed_linear_fit", "model_version": "v3",
        "metric": "observed_search_query_impressions",
        "source_metric": "observed_search_query_impressions",
        "prediction_ref": f"original_prediction_{n}",
        "horizon_days": 7,
        "observed_daily_values": observations,
        "actual_date": (last + timedelta(days=7)).isoformat(),
        "actual_value": float(20+n),
        "actual_evidence_ref": f"original-outcome:{n}",
    }


def test_uncalibrated_sources_never_become_live_production_queue():
    result = queue()
    assert result["queue_type"] == "RESEARCH_ONLY_NOT_PUBLISH_QUEUE"
    assert len(result["rows"]) == 2
    assert result["publishable_count"] == 0
    assert all(row["production_slot_authorized"] is False for row in result["rows"])
    assert all(row["verified_page_sessions"] is None for row in result["rows"])
    assert all(row["research_priority_not_forecast"] for row in result["rows"])


def test_queue_binds_gsc_exact_source_without_inventing_geo_search_volume():
    specs = inputs()
    from tests.test_microsite_source_and_copy_v2_20261027 import receipt
    # This test uses a real factory source contract with no exact evidence.
    gsc = connect_factory_to_gsc(specs, receipt())
    comm = build_microsite_commercial_review(specs, now=NOW)
    result = build_ranked_microsite_queue(specs, gsc=gsc, commercial=comm)
    assert all(row["exact_first_party_query_observed"] is False for row in result["rows"])


def test_forecast_calibration_original_review_computes_errors_but_not_independent_source_proof():
    raw = [historical_case(n) for n in range(3)]
    result = review_historical_model_calibration(raw)
    assert result["historical_pairs_checked"] == 3
    assert result["verified_model_count"] == 0
    assert result["models"][0]["mean_absolute_error"] is None
    assert result["models"][0]["out_of_sample_evaluations"] == 0


def test_original_custody_verifier_marks_only_independently_verified_historical_outcomes():
    inspected = []
    def owner_verifier(ref, metric, evidence_refs, digest, issued_at):
        inspected.append(ref)
        return bool(ref and metric and evidence_refs and len(digest) == 64 and issued_at)
    model = review_historical_model_calibration(
        [historical_case(n) for n in range(3)],
        verify_original_source=owner_verifier)
    assert len(inspected) == 3
    assert model["models"][0]["calibration_evidence_verified"] is True
    assert model["models"][0]["out_of_sample_evaluations"] == 3
    assert model["models"][0]["mean_absolute_error"] is not None
    # Pure unit-test stub is NOT real source custody, no production model changed.
    assert model["no_live_forecast_mutation"] is True


def test_mismatched_original_forecast_actual_is_not_calibrated():
    case = historical_case()
    case["actual_date"] = (date.fromisoformat(case["actual_date"]) - timedelta(days=1)).isoformat()
    result = review_historical_model_calibration([case], verify_original_source=lambda *args: True)
    assert result["verified_model_count"] == 0
    assert result["models"][0]["out_of_sample_evaluations"] == 0


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(source_owner="not_predictive_registry"),
    lambda x: x.update(metric="crypto_price"),
    lambda x: x.update(horizon_days=999),
    lambda x: x.update(observed_daily_values=[]),
])
def test_bad_calibration_cases_held(mutation):
    case = historical_case()
    mutation(case)
    with pytest.raises(ValueError):
        review_historical_model_calibration([case])


def test_duplicate_predictions_rejected():
    case = historical_case()
    with pytest.raises(ValueError, match="reused"):
        review_historical_model_calibration([case, case])


def test_no_real_factory_page_release_keeps_outcome_counts_missing():
    outcomes = build_microsite_outcome_register(queue())
    assert outcomes["factory_page_count"] == 2
    assert outcomes["factory_pages_with_verified_sessions"] == 0
    for row in outcomes["pages"]:
        assert row["measurement_state"] == "NOT_RELEASED_BY_ORIGINAL_SITE_OWNER"
        assert row["traffic"]["gsc_impressions"] is None
        assert row["funnel"]["consented_enquiry_submissions"] is None
        assert row["funnel"]["settled_revenue_minor"] is None
        assert row["funnel"]["attribution_join_verified"] is False


def test_self_supplied_release_cannot_authorize_fake_analytics_or_payment():
    with pytest.raises(ValueError, match="original owner"):
        build_microsite_outcome_register(
            queue(), trusted_approved_page_readback={
                "status": "approved", "revenue": 250000,
            })


def test_existing_seo_baseline_is_not_relabelled_microsite_metrics(tmp_path):
    original = {
        "schema_version": "empire.search.weekly_two_page_outcome_observer.v1",
        "status": "READ_ONLY_WEEKLY_REPORT",
        "source_property": "sc-domain:empire-ai.co.uk",
        "dimensions": ["page"],
        "website_mutations": False, "realised_revenue_verified": False,
        "qualified_buyer_enquiries_verified": False, "execution_authority": "NONE",
        "current_window": {"start_date": "2026-10-16", "end_date": "2026-10-22",
                           "pages": [{
                               "url": "https://empire-ai.co.uk/predictive-revenue",
                               "status": "MEASURED_PAGE_METRICS",
                               "clicks": 0, "impressions": 1,
                               "evidence_refs": ["gsc-row:source"]
                           }, {
                               "url": "https://empire-ai.co.uk/industries/roofing",
                               "status": "NO_PAGE_IN_RETURNED_GSC_ROWS",
                               "clicks": None, "impressions": None,
                               "evidence_refs": [],
                           }]},
    }
    path = tmp_path / "weekly.json"
    path.write_text(json.dumps(original))
    parsed = read_original_weekly_search_report(path)
    scorecard = build_microsite_outcome_register(queue(), original_weekly_gsc=parsed)
    pages = scorecard["comparison_baseline"]["baseline_pages"]
    assert pages[0]["impressions"] == 1
    assert pages[0]["search_clicks"] == 0
    assert pages[1]["search_clicks"] is None
    assert pages[0]["is_microsite_factory_page"] is False
    assert all(page["traffic"]["gsc_impressions"] is None for page in scorecard["pages"])


def test_forged_queue_metrics_rejected():
    result = queue()
    result["rows"][0]["production_slot_authorized"] = True
    with pytest.raises(ValueError, match="production"):
        build_microsite_outcome_register(result)


def test_per_page_measurement_held_without_original_website_owner_reader():
    from empire_os.microsite_approved_page_measurement_v4 import review_deployed_microsite
    example = inputs()[0]
    result = review_deployed_microsite(example)
    assert result["state"] == "UNRELEASED_OR_RELEASE_NOT_PROVEN"
    assert result["organic_search_clicks"] is None
    assert result["consented_enquiries"] is None
    assert result["settled_revenue_minor"] is None
    assert result["attributed_revenue_verified"] is False


def test_strict_future_source_adapters_join_by_exact_candidate_asset_and_url():
    from empire_os.microsite_approved_page_measurement_v4 import review_deployed_microsite
    from empire_os.predictive_microsite_factory import build_candidate
    import hashlib
    spec = inputs()[0]
    original, html = build_candidate(spec)
    cid = original["id"]
    digest = hashlib.sha256(html.encode()).hexdigest()
    url = "https://empire-ai.co.uk/research/test-owner-release"
    def binding(source):
        return {
            "source_owner": source, "candidate_id": cid, "asset_sha256": digest,
            "public_url": url, "source_evidence_ref": f"owner:source:{source}"
        }
    release = {**binding("original_empire_website_owner"),
               "status": "ORIGINAL_OWNER_DEPLOYMENT_READBACK_VERIFIED"}
    gsc = {**binding("original_seo_first_party_gsc"),
           "dimension": "page", "status": "MEASURED_PAGE_METRICS",
           "clicks": 2, "impressions": 11}
    web_events = {**binding("original_website_consent_and_event_owner"),
                  "lawful_website_analytics_consent_verified": True,
                  "server_side_event_collection_verified": True, "sessions": 8}
    crm = {**binding("original_empire_crm_owner"),
           "source_to_enquiry_identity_join_verified": True,
           "consent_and_suppression_verified": True, "consented_enquiries": 2,
           "qualified_enquiries": 1, "buyer_accepted_events": 1}
    settled = {**binding("original_empire_verified_settlement_owner"),
               "original_accepted_event_to_settlement_join_verified": True,
               "cash_settled_independently_verified": True,
               "settled_revenue_minor": 5000, "currency": "USD"}
    # These callbacks are synthetic test doubles, NOT active EmpireOS sources.
    measured = review_deployed_microsite(
        spec, original_site_owner_reader=lambda _: release,
        original_gsc_reader=lambda _: gsc,
        original_first_party_reader=lambda _: web_events,
        original_crm_reader=lambda _: crm,
        original_settlement_reader=lambda _: settled)
    assert measured["state"] == "OWNER_DEPLOYMENT_VERIFIED_MEASUREMENT_PENDING"
    assert measured["organic_search_clicks"] == 2
    assert measured["consent_verified_sessions"] == 8
    assert measured["buyer_accepted_events"] == 1
    assert measured["settled_revenue_minor"] == 5000
    assert measured["attributed_revenue_verified"] is True


def test_forged_owner_approval_and_mismatched_source_rejected():
    from empire_os.microsite_approved_page_measurement_v4 import review_deployed_microsite
    with pytest.raises(ValueError, match="unverified site-owner"):
        review_deployed_microsite(inputs()[0], original_site_owner_reader=lambda _: {
            "status": "approved", "public_url": "https://empire-ai.co.uk/research/fake"
        })


def test_calibration_original_issued_digest_must_precede_actual_outcome():
    original = historical_case()
    original["issued_at"] = "2026-11-01T00:00:00Z"
    result = review_historical_model_calibration(
        [original], verify_original_source=lambda *args: True)
    assert result["verified_model_count"] == 0
    original["original_immutable_forecast_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original pre-outcome"):
        review_historical_model_calibration([original])
