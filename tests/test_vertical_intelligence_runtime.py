import json

from empire_os.vertical_intelligence_runtime import (
    build_private_capital_intelligence_runtime,
    build_property_intelligence_runtime,
)


def test_property_runtime_reuses_only_observed_permit_and_physical_evidence(tmp_path):
    permit_path = tmp_path / "runtime/acquisition/signal_inbox.json"
    permit_path.parent.mkdir(parents=True)
    permit_path.write_text(json.dumps({
        "p1": {
            "source": "permits_nyc",
            "status": "resolved",
            "metro": "NYC",
            "created_at": "2026-09-21T10:00:00+00:00",
            "last_seen_at": "2026-09-21T11:00:00+00:00",
            "url": "https://example.test/permit/1",
            "raw": {"job__": "1"},
        }
    }))

    strike = tmp_path / "runtime/revenue_strike"
    strike.mkdir(parents=True)
    (strike / "one.json").write_text(json.dumps({
        "execution_authority": "none",
        "market": "Dallas-Fort Worth, TX",
        "observed_at": "2026-09-21T12:00:00+00:00",
        "trigger": {
            "source": "NWS",
            "modeled_multiplier": 2.0,
        },
    }))

    result = build_property_intelligence_runtime(tmp_path)

    assert result["permit_signal_count"] == 1
    assert result["physical_observation_count"] == 1
    assert result["evidence_count"] == 2
    assert result["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert result["opportunity_count"] is None
    assert result["pricing_observed"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_private_capital_runtime_stays_unknown_without_snapshot(tmp_path):
    result = build_private_capital_intelligence_runtime(tmp_path)

    assert result["snapshot_available"] is False
    assert result["evidence_state"] == "UNKNOWN"
    assert result["evidence_count"] is None
    assert result["deal_intent_observed"] is False
    assert result["opportunity_count"] is None
    assert result["actual_revenue"] is False


def test_private_capital_runtime_reads_only_explicit_canonical_counts(tmp_path):
    path = tmp_path / "runtime/vertical_intelligence/private_capital_latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "generated_at": "2026-09-21T20:00:00+00:00",
        "canonical_signal_count": 2,
        "canonical_fact_count": 3,
        "segment_membership_count": 1,
        "latest_observed_at": "2026-09-21T19:59:00+00:00",
    }))

    result = build_private_capital_intelligence_runtime(tmp_path)

    assert result["snapshot_available"] is True
    assert result["evidence_count"] == 6
    assert result["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert result["deal_intent_observed"] is False
    assert result["actual_revenue"] is False
