"""Original NOAA -> canonical source reference -> PRIME obs read-model tests."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from empire_os.nws_official_source_provenance import review_nws_alert_payload
from empire_os.predictive_cloud_official_source_bridge import (
    review_official_source_for_prime,
)
from empire_os.predictive_revenue_brain_bridge import (
    build_predictive_revenue_brain_review,
)
from empire_os.predictive_revenue_prime_status import read_prime_founder_status

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def source_review(when=NOW):
    return review_nws_alert_payload({
        "features": [{
            "id": "https://api.weather.gov/alerts/urn:oid:sample.123",
            "type": "Feature",
            "properties": {
                "sent": (when - timedelta(minutes=50)).isoformat(),
                "event": "Tornado Warning", "areaDesc": "Example private test county",
                "status": "Actual", "messageType": "Alert",
                "severity": "Severe", "certainty": "Likely",
                "urgency": "Immediate",
                "headline": "person@example.com never surfaced",
            },
        }],
    }, observed_at=when, official_https_response_verified=False)


def brain(**kwargs):
    return build_predictive_revenue_brain_review(
        tenant_id="empire-internal", as_of=NOW, **kwargs
    )


def test_observed_weather_reference_is_not_a_prime_opportunity_or_forecast():
    raw = source_review()
    result = brain(official_nws_source_review=raw)
    source = result["official_source_observatory"]
    assert source["schema_version"] == "empire.predictive_cloud.official_source_observatory.v1"
    assert source["status"] == "STRUCTURALLY_REVIEWED_NO_ECONOMIC_AUTHORITY"
    assert source["source_references_reviewed"] == 1
    assert source["freshness"] == "RECENT_REVIEW_UNATTESTED"
    assert source["source_custody_independently_verified"] is False
    assert source["economic_signal_admitted"] is False
    assert source["source_observations_promoted_to_opportunities"] == 0
    assert source["source_observations_added_to_prime_scenarios"] == 0
    assert source["property_damage_verified"] is False
    assert result["opportunity_count"] == 0
    assert result["prime_scenarios"] is None
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False
    assert result["recognized_revenue_cents"] is None
    assert result["official_source_records_are_not_opportunities"] is True
    assert "person@example.com" not in str(result)
    assert "Example private test county" not in str(result)


def test_absent_source_is_unknown_not_verified_zero():
    row = brain()
    source = row["official_source_observatory"]
    assert source["status"] == "NOT_CONNECTED"
    assert source["source_references_reviewed"] is None
    assert source["qualifying_commercial_opportunities"] is None
    assert row["source_freshness"]["official_nws"] == "UNKNOWN"


def test_explicit_valid_zero_alert_review_is_not_all_weather_zero():
    raw = review_nws_alert_payload({"features": []}, observed_at=NOW)
    source = review_official_source_for_prime(nws_review=raw, as_of=NOW)
    assert source["status"] == "REVIEWED_NO_CURRENT_SOURCE_RECORDS"
    assert source["source_references_reviewed"] == 0
    assert source["qualifying_commercial_opportunities"] is None
    assert source["revenue_verified"] is False


def test_stale_observation_will_never_validate_as_current():
    raw = source_review(NOW - timedelta(days=4))
    reviewed = review_official_source_for_prime(nws_review=raw, as_of=NOW)
    assert reviewed["status"] == "STALE_SOURCE_REVIEW"
    assert reviewed["freshness"] == "STALE"
    assert "SOURCE_REVIEW_STALE" in reviewed["blockers"]


def test_source_review_not_mutated_when_composed():
    inp = source_review()
    before = deepcopy(inp)
    brain(official_nws_source_review=inp)
    assert inp == before


@pytest.mark.parametrize("mutator", [
    lambda r: r.update(mode="EXECUTE"),
    lambda r: r.update(execution_authority="execute"),
    lambda r: r.update(economic_signal_eligible=True),
    lambda r: r.update(recognized_revenue=True),
    lambda r: r.update(database_written=True),
    lambda r: r.update(gpu_spend_cents=100),
    lambda r: r["universal_custody_review"].update(mode="EXECUTE"),
    lambda r: r["universal_custody_review"].update(empiredb_write=True),
    lambda r: r["universal_custody_review"].update(recognized_revenue_cents=100),
    lambda r: r["universal_custody_review"].update(source_count_structurally_reviewed=100),
    lambda r: r["universal_custody_review"].update(category_counts={"NEWS": 1}),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(provider="licensed_markets"),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(buyer_intent_verified=True),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(economic_signal_eligible=True),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(licensed_for_downstream_use=True),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(
        evidence_fingerprint="not-a-hash"
    ),
    lambda r: r["universal_custody_review"]["reviewed_sources"][0].update(
        observed_at=(NOW+timedelta(hours=1)).isoformat()
    ),
    lambda r: r["universal_custody_review"]["reviewed_sources"].append(
        r["universal_custody_review"]["reviewed_sources"][0]
    ),
])
def test_cannot_promote_untrusted_source_with_input_injection(mutator):
    r = source_review()
    mutator(r)
    with pytest.raises(ValueError):
        brain(official_nws_source_review=r)


def test_private_founder_aggregate_source_fields_no_data_or_identity(tmp_path):
    raw = source_review()
    result = read_prime_founder_status(
        repo_root=tmp_path, as_of=NOW, official_nws_source_review=raw
    )
    assert result["official_nws_review_status"] == "STRUCTURALLY_REVIEWED_NO_ECONOMIC_AUTHORITY"
    assert result["official_nws_source_reference_count"] == 1
    assert result["official_nws_source_freshness"] == "RECENT_REVIEW_UNATTESTED"
    assert result["official_nws_is_commercial_opportunity"] is False
    assert result["prime_simulation_status"] == "NOT_RUN_NO_VERIFIED_CRM_INPUT"
    assert result["realized_revenue_cents"] is None
    assert "person@example.com" not in str(result)
    assert "urn:oid:" not in str(result)
    assert "tenant_id" not in str(result)


def test_bad_official_source_status_fail_closed_in_founder_surface(tmp_path):
    inp = source_review()
    inp["economic_signal_eligible"] = True
    result = read_prime_founder_status(
        repo_root=tmp_path, as_of=NOW, official_nws_source_review=inp
    )
    assert result["status"] == "READ_ONLY_SOURCE_REVIEW_UNAVAILABLE"
    assert result["official_nws_source_reference_count"] is None
    assert result["revenue_verified"] is False
