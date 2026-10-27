"""Commercial intelligence from original buyer ZIP observer and V3 registry.

No DB, network, routing or production calls inside tests.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import runpy
from pathlib import Path
import json

import pytest

from empire_os.microsite_commercial_intelligence_v3 import (
    buyer_targeting_observation, forecast_observation, build_microsite_commercial_review,
    read_original_buyer_snapshot,
)
from empire_os.predictive_cloud_v3 import DirectionalForecast
from empire_os.predictive_registry import ForecastRegistryRecord

NOW = datetime(2026, 10, 27, 10, 18, tzinfo=timezone.utc)
SAMPLE = Path(__file__).with_name("test_predictive_microsite_factory_20261026.py")


def spec():
    row = runpy.run_path(str(SAMPLE))["candidate"]()
    row["geography"] = {
        "market_id": "US-IL", "kind": "us_zip",
        "area": "60601", "market_match_verified": False,
        "evidence_refs": ["coverage:row:60601"],
    }
    row["buyer_signal"] = {"buyer_key": "lead_smart", "service": "roofing"}
    return row


def snapshot():
    timestamp = NOW.isoformat()
    return {
        "schema_version": "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "observed_at": timestamp,
        "source": {"table": "offer_bids", "semantics": "TARGETING_GUIDANCE_ONLY",
                   "payout_guaranteed": False},
        "coverage": {"source_newest_last_updated": timestamp},
        "authority": {
            "execution_authority": "NONE",
            "tracking_verified": False,
            "routing_verified": False,
            "routing_enabled": False,
            "traffic_enabled": False,
            "zip_coverage_activation_verified": False,
        },
        "rows": [{
            "zip": "60601", "offer_name": "Roofing Nationwide",
            "top_payout": 25, "duration_payout": None, "cpl_payout": None,
            "last_updated": timestamp,
        }],
    }


def valid_registry_row(original):
    f = DirectionalForecast(
        available=True, metric="observed_search_query_impressions",
        horizon_days=7, sample_count=15, latest_observed_value=8.0,
        predicted_value=9.5, daily_slope=0.1, r_squared=0.6,
        evidence_confidence=0.3, direction="up", reason=None,
        source="canonical_observed_time_series",
    )
    evidence = {
        "microsite_market_id": original["geography"]["market_id"],
        "microsite_area": original["geography"]["area"],
        "microsite_area_kind": original["geography"]["kind"],
        "microsite_keyword": original["keyword_opportunity"]["keyword"],
        "scope_authorized_for_microsite_research": True,
        "evidence_refs": ["owned-first-party:query"],
    }
    record = ForecastRegistryRecord(
        forecast_key="research-chicago-roofing",
        model_name="observed_linear_fit",
        model_version="v3",
        dimension_key="US-IL:roofing:60601",
        forecast=f, evidence=evidence,
    )
    row = {
        "forecast_key": record.forecast_key, "model_name": record.model_name,
        "model_version": record.model_version, "dimension_key": record.dimension_key,
        "metric": f.metric, "horizon_days": f.horizon_days,
        "sample_count": f.sample_count,
        "latest_observed_value": f.latest_observed_value,
        "predicted_value": f.predicted_value,
        "daily_slope": f.daily_slope,
        "r_squared": f.r_squared,
        "evidence_confidence": f.evidence_confidence,
        "direction": f.direction, "source": f.source,
        "generated_at": NOW.isoformat(),
        "evidence": {**evidence, "registry_payload_sha256": record.payload_sha256},
    }
    return row


def with_binding():
    s = spec()
    s["predictive_forecast_binding"] = {
        "forecast_key": "research-chicago-roofing",
        "dimension_key": "US-IL:roofing:60601",
        "metric": "observed_search_query_impressions",
    }
    return s


def test_original_coverage_lookup_is_research_not_traffic():
    observation = buyer_targeting_observation(
        spec(), snapshot=snapshot(),
        snapshot_sha256="ab" * 32, now=NOW)
    assert observation["status"] == "TARGETING_GUIDANCE_ONLY"
    assert observation["coverage_observed"] is True
    assert observation["targeting_candidate"] is True
    assert observation["live_route_eligible"] is False
    assert observation["qualified_payer_verified"] is False
    assert observation["tracked_accepted_revenue"] is None


def test_stale_snapshot_rejected_as_commercial_route():
    old = snapshot()
    old["observed_at"] = (NOW - timedelta(hours=8)).isoformat()
    result = buyer_targeting_observation(spec(), snapshot=old, now=NOW)
    assert result["status"] == "STALE_TARGETING_GUIDANCE"
    assert result["live_route_eligible"] is False


def test_no_buyer_signal_not_auto_matched_to_external_partner():
    s = spec()
    del s["buyer_signal"]
    row = buyer_targeting_observation(s, snapshot=snapshot(), now=NOW)
    assert row["status"] == "BUYER_PATH_UNSPECIFIED"


def test_non_zip_or_unsupported_buyer_not_accepted():
    s = spec()
    s["geography"] = {"market_id": "US-IL", "kind": "metro", "area": "Chicago, IL"}
    assert buyer_targeting_observation(s, snapshot=snapshot(), now=NOW)["status"] == "BUYER_ZIP_REQUIRED"
    s["buyer_signal"]["buyer_key"] = "invented_partner"
    with pytest.raises(ValueError):
        buyer_targeting_observation(s, snapshot=snapshot(), now=NOW)


def test_invalid_coverage_source_rejected():
    s = snapshot()
    s["source"]["payout_guaranteed"] = True
    with pytest.raises(ValueError):
        buyer_targeting_observation(spec(), snapshot=s, now=NOW)


def test_canonical_forecast_digest_and_exact_binding_preserve_prediction_vs_truth():
    s = with_binding()
    record = valid_registry_row(s)
    result = forecast_observation(s, [record], now=NOW)
    assert result["status"] == "OBSERVED_PREDICTIVE_RESEARCH_SIGNAL"
    assert result["verified_forecast_registry_record"] is True
    assert result["direction"] == "up"
    assert result["predicted_value"] == 9.5
    assert result["forecast_is_buyer_or_conversion_proof"] is False
    assert result["actual_revenue_verified"] is False


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r.update(predicted_value=200), "FORECAST_PROVENANCE_INVALID"),
    (lambda r: r.update(evidence={**r["evidence"], "microsite_keyword": "solar"}), "FORECAST_SCOPE_NOT_VERIFIED"),
    (lambda r: r.update(evidence={**r["evidence"], "scope_authorized_for_microsite_research": False}), "FORECAST_SCOPE_NOT_VERIFIED"),
    (lambda r: r.update(evidence={**r["evidence"], "registry_payload_sha256": "0" * 64}), "FORECAST_PROVENANCE_INVALID"),
    (lambda r: r.update(generated_at=(NOW - timedelta(hours=72)).isoformat()), "FORECAST_OUTSIDE_FRESHNESS_WINDOW"),
])
def test_bad_or_stale_forecast_never_escalates(mutation, reason):
    s = with_binding()
    r = valid_registry_row(s)
    mutation(r)
    out = forecast_observation(s, [r], now=NOW)
    assert out["status"] == reason
    assert out["verified_forecast_registry_record"] is False


def test_ambiguous_forecast_entries_are_rejected():
    s = with_binding()
    row = valid_registry_row(s)
    result = forecast_observation(s, [row, deepcopy(row)], now=NOW)
    assert result["status"] == "FORECAST_AMBIGUOUS"


def test_forecast_needs_supported_metric_not_arbitrary_crypto_series():
    s = with_binding()
    s["predictive_forecast_binding"]["metric"] = "btc_price"
    with pytest.raises(ValueError, match="unsupported"):
        forecast_observation(s, [], now=NOW)


def test_commercial_review_produces_research_packet_never_domain_publishing():
    s = with_binding()
    data = build_microsite_commercial_review(
        [s], buyer_snapshot=snapshot(), buyer_snapshot_sha256="ab" * 32,
        forecast_rows=[valid_registry_row(s)], now=NOW)
    assert data["research_candidates_with_observed_buyer_coverage"] == 1
    assert data["candidates_with_valid_forecast_records"] == 1
    assert data["publishable_candidates"] == 0
    assert data["candidates"][0]["revenue_verified"] is False
    assert data["candidates"][0]["automated_domain_spinning_enabled"] is False
    assert data["published"] is False


def test_missing_forecast_stays_missing_without_automatic_fallback():
    s = with_binding()
    review = build_microsite_commercial_review([s], buyer_snapshot=None, forecast_rows=None, now=NOW)
    assert review["candidates"][0]["buyer_targeting"]["status"] == "BUYER_COVERAGE_SOURCE_MISSING"
    assert review["candidates"][0]["predictive_forecast"]["status"] == "FORECAST_SOURCE_MISSING"
    assert review["publishable_candidates"] == 0


def test_original_snapshot_loader_rejects_symlink(tmp_path):
    p = tmp_path / "snapshot.json"
    p.write_text(json.dumps(snapshot()), encoding="utf-8")
    loaded, digest = read_original_buyer_snapshot(p)
    assert loaded["mode"] == "OBSERVE" and len(digest) == 64
    symlink = tmp_path / "link"
    symlink.symlink_to(p)
    with pytest.raises(ValueError):
        read_original_buyer_snapshot(symlink)


def test_cli_combines_original_buyer_reader_and_draft_only_outputs(tmp_path, monkeypatch):
    """Integration: canonical buyer snapshot -> private manifest; no live release."""
    from scripts import review_predictive_microsite_factory_20261026 as cli
    now = datetime.now(timezone.utc).isoformat()
    original = snapshot()
    original["observed_at"] = now
    original["coverage"]["source_newest_last_updated"] = now
    original["rows"][0]["last_updated"] = now
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(cli, "ORIGINAL_BUYER_COVERAGE", source_path)
    opportunity = spec()
    opportunity["keyword_opportunity"]["observed_demand"] = None
    in_path = tmp_path / "candidate.json"
    in_path.write_text(json.dumps(opportunity), encoding="utf-8")
    out_dir = tmp_path / "qa"
    manifest = cli.run(in_path, out_dir, observe_original_buyer_coverage=True)
    assert manifest["held"] == 1
    assert manifest["publishable_candidates"] == 0
    assert manifest["observed_original_buyer_coverage"] is True
    result = json.loads((out_dir / "commercial_research_review.json").read_text())
    assert result["research_candidates_with_observed_buyer_coverage"] == 1
    assert result["candidates"][0]["buyer_targeting"]["live_route_eligible"] is False
    preview = (out_dir / manifest["previews"][0]).read_text()
    assert 'content="noindex,nofollow,noarchive"' in preview
    assert "data:image/svg+xml;base64," in preview
    assert "Commercial verification" in preview
    assert (out_dir / "manifest.json").is_file()
    assert not (out_dir / "production_release.json").exists()


def test_existing_predictive_registry_reader_called_only_when_explicit():
    from empire_os.microsite_commercial_intelligence_v3 import read_original_predictive_registry
    seen = []
    def reader(*, limit):
        seen.append(limit)
        return [{"forecast_key": "future-research-only"}]
    assert read_original_predictive_registry("dedicated_read_role", reader=reader, limit=10) == [
        {"forecast_key": "future-research-only"}
    ]
    assert seen == [10]
    with pytest.raises(ValueError, match="DSN"):
        read_original_predictive_registry("", reader=reader)
    with pytest.raises(ValueError, match="limit"):
        read_original_predictive_registry("dedicated_read_role", limit=501, reader=reader)


def test_optin_registry_read_is_separate_from_buyer_and_cannot_publish(tmp_path, monkeypatch):
    from scripts import review_predictive_microsite_factory_20261026 as cli
    example = spec()
    example["predictive_forecast_binding"] = {
        "forecast_key": "research-chicago-roofing",
        "metric": "observed_search_query_impressions",
        "dimension_key": "US-IL:roofing:60601",
    }
    example["keyword_opportunity"]["observed_demand"] = None
    input_file = tmp_path / "candidate.json"
    input_file.write_text(json.dumps(example), encoding="utf-8")
    monkeypatch.setenv("EMPIRE_PREDICTIVE_REGISTRY_DSN", "read_only_test_credential")
    captured = []
    def reader(*, limit):
        captured.append(limit)
        return [valid_registry_row(example)]
    out_dir = tmp_path / "previews"
    summary = cli.run(
        input_file, out_dir,
        read_original_forecast_registry=True,
        forecast_reader=reader,
    )
    assert captured == [100]
    assert summary["original_predictive_registry_read"] is True
    assert summary["verified_forecast_records"] == 1
    assert summary["publishable_candidates"] == 0
    commercial = json.loads((out_dir / "commercial_research_review.json").read_text())
    assert commercial["candidates"][0]["predictive_forecast"]["actual_revenue_verified"] is False


def test_no_credential_refuses_original_forecast_reader_even_if_mocked(tmp_path, monkeypatch):
    from scripts import review_predictive_microsite_factory_20261026 as cli
    monkeypatch.delenv("EMPIRE_PREDICTIVE_REGISTRY_DSN", raising=False)
    p = tmp_path / "example.json"
    p.write_text(json.dumps(spec()), encoding="utf-8")
    with pytest.raises(ValueError, match="DSN"):
        cli.run(p, tmp_path / "previews",
                read_original_forecast_registry=True,
                forecast_reader=lambda *, limit: [])
    assert not (tmp_path / "previews").exists()
