"""Offline tests for one NWS source, original storm and tenant boundaries."""
from datetime import datetime, timedelta, timezone
import io
import json

import pytest

from empire_os.economic_signal_fabric import (
    EconomicSignalError, validate_economic_signal,
)
from empire_os.nws_official_source_provenance import (
    fetch_nws_active_alerts_once, review_nws_alert_payload,
    review_canonical_tenant_entity_binding, MAX_FEATURES,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
TENANT = "a5f7cba7-4cf1-4f03-9a53-a88e9c0b412e"
ENTITY = "86c607b6-2bb2-43ae-b572-77a98929cb79"


def feature(number=1, **props):
    base = {
        "sent": (NOW - timedelta(hours=2)).isoformat(),
        "event": "Severe Thunderstorm Warning",
        "areaDesc": "Example test county",
        "status": "Actual", "messageType": "Alert",
        "severity": "Severe", "certainty": "Likely", "urgency": "Immediate",
        "headline": "Should never appear in output: private@example.com",
    }
    base.update(props)
    return {
        "id": "https://api.weather.gov/alerts/urn:oid:example." + str(number),
        "type": "Feature",
        "properties": base,
        "geometry": {"type": "Point", "coordinates": [-95, 32]},
    }


def test_one_nws_source_flows_through_original_storm_and_universal_review():
    row = review_nws_alert_payload({"features": [feature()]}, observed_at=NOW)
    cust = row["universal_custody_review"]
    assert cust["source_count_structurally_reviewed"] == 1
    assert cust["category_counts"] == {"ENVIRONMENT": 1}
    assert row["source_adapter"] == "existing_storm_predictor_and_spatial_physical_adapters"
    assert row["transport_observed"] is False
    assert cust["reviewed_sources"][0]["existing_storm_evidence_adapter_used"] is True
    assert cust["reviewed_sources"][0]["independent_source_verified"] is False
    assert cust["reviewed_sources"][0]["economic_signal_eligible"] is False
    assert row["buyer_intent_verified"] is False
    assert row["property_damage_verified"] is False
    assert row["recognized_revenue"] is False
    assert row["redis_written"] is False
    assert row["database_written"] is False
    assert row["crm_written"] is False
    assert row["notifications_sent"] is False
    assert row["execution_authority"] == "none"
    assert "private@example.com" not in str(row)
    assert "Example test county" not in str(row)


def test_duplicate_alerts_are_rejected_by_original_universal_dedup():
    result = review_nws_alert_payload(
        {"features": [feature(), feature()]}, observed_at=NOW,
    )["universal_custody_review"]
    assert result["source_count_structurally_reviewed"] == 1
    assert result["source_count_rejected"] == 1


@pytest.mark.parametrize("tamper", [
    {"sent": (NOW + timedelta(minutes=1)).isoformat()},
    {"sent": "2026-10-24T13:00:00"},
    {"sent": "not-a-time"},
    {"event": {"type": "not-nws"}},
])
def test_invalid_feature_fails_without_promotion(tamper):
    row = review_nws_alert_payload({"features": [feature(**tamper)]}, observed_at=NOW)
    assert row["universal_custody_review"]["source_count_structurally_reviewed"] == 0
    assert row["shape_rejections"]
    assert row["buyer_intent_verified"] is False


def test_untrusted_feature_id_host_rejected():
    row = feature()
    row["id"] = "https://api.weather.gov.attacker.invalid/alerts/123"
    result = review_nws_alert_payload({"features": [row]}, observed_at=NOW)
    assert result["universal_custody_review"]["source_count_structurally_reviewed"] == 0
    assert result["shape_rejections"]


def test_no_automatic_fetch():
    with pytest.raises(PermissionError, match="explicit"):
        fetch_nws_active_alerts_once()


def test_no_unbounded_fetch():
    with pytest.raises(ValueError, match="bounded"):
        fetch_nws_active_alerts_once(enable_official_read=True, max_bytes=0)


class _Response:
    status = 200
    def __init__(self, raw):
        self.data = io.BytesIO(raw)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.data.read(size)


class _Transport:
    def __init__(self, contents, status=200):
        self.contents = contents
        self.status = status
        self.calls = 0
    def open(self, req, *, timeout):
        self.calls += 1
        assert req.get_full_url() == "https://api.weather.gov/alerts/active?area=IL"
        assert req.get_method() == "GET"
        assert "EmpireOS" in req.get_header("User-agent")
        assert timeout == 8
        resp = _Response(self.contents)
        resp.status = self.status
        return resp


def test_injected_transport_reads_once_without_side_effects():
    fake = _Transport(json.dumps({"features": []}).encode())
    reviewed = fetch_nws_active_alerts_once(
        enable_official_read=True, transport=fake,
    )
    assert fake.calls == 1
    assert reviewed["transport_observed"] is True
    assert reviewed["recognized_revenue"] is False
    assert reviewed["universal_custody_review"]["source_count_structurally_reviewed"] == 0


def test_nws_non200_payload_too_large_and_invalid_json_all_fail_closed():
    with pytest.raises(ValueError, match="non-success"):
        fetch_nws_active_alerts_once(
            enable_official_read=True, transport=_Transport(b"{}", status=429),
        )
    with pytest.raises(ValueError, match="exceeds"):
        fetch_nws_active_alerts_once(
            enable_official_read=True, transport=_Transport(b"X" * 100),
            max_bytes=20,
        )
    with pytest.raises(ValueError, match="valid JSON"):
        fetch_nws_active_alerts_once(
            enable_official_read=True, transport=_Transport(b"not json"),
        )


def test_bounded_payload_and_absent_features_rejected():
    with pytest.raises(ValueError, match="features"):
        review_nws_alert_payload({}, observed_at=NOW)
    with pytest.raises(ValueError, match="bounded"):
        review_nws_alert_payload(
            {"features": [feature()] * (MAX_FEATURES + 1)}, observed_at=NOW,
        )


def test_cannot_promote_weather_to_original_economic_fabric():
    row = review_nws_alert_payload({"features": [feature()]}, observed_at=NOW)
    raw = row["universal_custody_review"]["reviewed_sources"][0]
    with pytest.raises(EconomicSignalError):
        validate_economic_signal(raw, expected_tenant_id=TENANT, as_of=NOW)


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
    def execute(self, sql, params):
        self.queries.append((sql, params))
    def fetchall(self):
        return self.rows


def test_canonical_tenant_binding_uses_existing_reader_not_user_claim():
    start = NOW - timedelta(days=1)
    cur = _Cursor([(TENANT, ENTITY, "observed", "binding-receipt", start, None)])
    row = review_canonical_tenant_entity_binding(
        cur, tenant_id=TENANT, entity_id=ENTITY, as_of=NOW,
    )
    assert row["canonical_tenant_entity_binding"] == "EXISTING_BINDING_CONFIRMED"
    assert cur.queries
    assert "tenant_business_entity_bindings" in cur.queries[0][0]
    assert cur.queries[0][1][0:2] == (TENANT, ENTITY)
    assert row["weather_entity_causal_link_verified"] is False
    assert row["economic_signal_eligible"] is False
    assert "binding-receipt" not in str(row)


def test_cross_tenant_or_ambiguous_db_binding_held():
    cur = _Cursor([])
    held = review_canonical_tenant_entity_binding(
        cur, tenant_id=TENANT, entity_id=ENTITY, as_of=NOW,
    )
    assert held["canonical_tenant_entity_binding"] == "HELD"
    dup = _Cursor([(TENANT, ENTITY, "observed", "a", NOW, None)] * 2)
    assert review_canonical_tenant_entity_binding(
        dup, tenant_id=TENANT, entity_id=ENTITY, as_of=NOW,
    )["economic_signal_eligible"] is False


def test_api_has_no_implicit_connection():
    row = review_nws_alert_payload({"features": []}, observed_at=NOW)
    assert row["transport_observed"] is False
    assert row["canonical_source_registry_verified"] is False
    assert row["canonical_entity_tenant_binding_verified"] is False
    assert row["economic_signal_eligible"] is False


def test_end_to_end_original_tenant_scope_bridge_stays_observe_only():
    from empire_os.nws_official_source_provenance import review_nws_to_existing_canonical_scope
    start = NOW - timedelta(days=1)
    cur = _Cursor([(TENANT, ENTITY, "observed", "existing-owner-receipt", start, None)])
    out = review_nws_to_existing_canonical_scope(
        {"features": [feature()]}, observed_at=NOW,
        trusted_canonical_cursor=cur,
        authenticated_tenant_id=TENANT,
        canonical_entity_id=ENTITY,
    )
    assert out["source_review"]["universal_custody_review"]["source_count_structurally_reviewed"] == 1
    assert out["existing_empiredb_tenant_entity_scope_review"][
        "canonical_tenant_entity_binding"
    ] == "EXISTING_BINDING_CONFIRMED"
    assert out["canonical_source_provenance_verified"] is False
    assert out["storm_to_specific_entity_link_verified"] is False
    assert out["economic_signal_fabric_admission"].startswith("HELD")
    assert out["opportunity_or_lead_created"] is False
    assert out["buyer_verified"] is False
    assert out["revenue_verified"] is False
    assert out["database_written"] is False


def test_scope_bridge_requires_original_cursor_and_real_existing_source():
    from empire_os.nws_official_source_provenance import review_nws_to_existing_canonical_scope
    out = review_nws_to_existing_canonical_scope(
        {"features": [feature()]}, observed_at=NOW,
        authenticated_tenant_id=TENANT, canonical_entity_id=ENTITY,
    )
    assert out["existing_empiredb_tenant_entity_scope_review"][
        "canonical_tenant_entity_binding"
    ] == "HELD_AUTHENTICATED_CURSOR_REQUIRED"
    assert out["execution_authority"] == "none"
    blank = review_nws_to_existing_canonical_scope(
        {"features": []}, observed_at=NOW,
    )
    assert blank["existing_empiredb_tenant_entity_scope_review"][
        "canonical_tenant_entity_binding"
    ] == "NOT_ATTEMPTED_NO_SOURCE_RECORD"
