"""All construction source rows here are synthetic, test-only fixtures."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta

import pytest

from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_history import build_construction_history
from empire_os.data_exchange_predictive_review import (
    review_construction_prediction_cohort,
)

# Reuse Empire's EXISTING full canonical mock commercial-chain fixtures;
# they are not new or real buyers, predictions, orders or payments.
from test_verified_outcome_learning_continuity import (
    prediction as baseline_prediction,
    feedback as canonical_feedback,
)

NOW = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)
FIRST = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
SECOND = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
TENANT = "tenant-A"


def observation(at, status):
    return {
        "record_id": "1739547", "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land", "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": "https://www.planning.data.gov.uk/entity/1739547",
        "source_observed_at": at.isoformat(),
        "planning_permission_status": status,
        "site_area_hectares": "0.125127",
    }


def snapshots(changed=True):
    before = build_construction_preview(
        [observation(FIRST, "non-permissioned")], observed_at=FIRST,
    )
    after = build_construction_preview(
        [observation(SECOND, "permissioned" if changed else "non-permissioned")],
        observed_at=SECOND,
    )
    return [before, after]


def proper_pair(source=None):
    source = source or snapshots()
    ev = build_construction_history(source, assessed_at=NOW)["observed_changes"][0]
    pred = baseline_prediction()
    pred["data_product"] = "empire_construction_signals"
    pred["source_event_id"] = ev["event_id"]
    pred["evidence_refs"].append("empire:construction_change:" + ev["event_id"])
    return {"prediction": pred, "feedback": canonical_feedback()}


def run(pairs, source=None):
    return review_construction_prediction_cohort(
        source_snapshots=snapshots() if source is None else source,
        pairs=pairs,
        tenant_id=TENANT, assessed_at=NOW,
    )


def test_no_forecasts_does_not_create_predictions_or_fake_revenue():
    result = run([])
    assert result["review_status"] == "HOLD"
    assert result["blockers"] == [
        "INSUFFICIENT_VERIFIED_EVALUATION_COHORT",
        "NO_CANONICAL_FORECAST_OUTCOME_PAIRS",
        "OUTCOME_CLASS_COVERAGE_MISSING",
    ]
    assert result["reviewed_prediction_count"] == 0
    assert result["shadow_calibration"]["available"] is False
    assert result["source_observed_change_count"] == 1
    assert result["predictive_marketing_claim_ready"] is False
    assert result["customer_delivery_enabled"] is False
    assert result["execution_authority"] == "NONE"


def test_canonical_commercial_learning_is_reused_not_reimplemented():
    result = run([proper_pair()])
    assert result["review_status"] == "HOLD"
    assert result["shadow_calibration"]["brier_score"] == 0.16
    assert result["reviewed_prediction_count"] == 1
    link = result["prediction_lineage"][0]
    assert link["verified_commercial_outcome"] is True
    assert link["source_causation_established"] is False
    assert link["descriptive_brier"] == 0.16
    assert result["model_mutation"] is False
    assert result["actual_revenue_created"] is False
    assert result["holdout_verified"] is False


def test_without_actual_source_change_no_forecasts_can_claim_linkage():
    result = run([], source=snapshots(changed=False))
    assert "NO_OBSERVED_SOURCE_CHANGES" in result["blockers"]
    with pytest.raises(ValueError, match="historical evidence"):
        run([proper_pair()], source=snapshots(changed=False))


def test_duplicate_prediction_or_outcome_fail_closed():
    pair = proper_pair()
    with pytest.raises(ValueError, match="duplicate forecast"):
        run([pair, deepcopy(pair)])


@pytest.mark.parametrize("change,part", [
    ({"data_product": "other_product"}, "prediction"),
    ({"source_event_id": "0" * 64}, "prediction"),
    ({"evidence_refs": ["quant_prediction:original"]}, "prediction"),
    ({"predicted_at": "2026-09-25T12:00:00Z"}, "prediction"),
    ({"horizon_until": "2026-11-20T12:00:00Z"}, "prediction"),
    ({"predicted_at": "2026-10-01T12:00:00"}, "prediction"),
    ({"tenant_id": "tenant-B"}, "feedback"),
    ({"verified_outcome": False}, "feedback"),
    ({"synthetic": True}, "feedback"),
])
def test_fails_closed_on_unverified_lineage_or_time(change, part):
    pair = proper_pair()
    pair[part].update(change)
    with pytest.raises(ValueError):
        run([pair])


def test_private_data_fields_not_collected_into_result():
    pair = proper_pair()
    pair["prediction"]["private_note"] = "DO NOT REPRODUCE"
    result = run([pair])
    assert "DO NOT REPRODUCE" not in str(result)
    assert "cortex_packet" not in str(result)


def test_malformed_cohort_and_tenant_fail_closed():
    with pytest.raises(ValueError, match="tenant"):
        review_construction_prediction_cohort(
            source_snapshots=snapshots(), pairs=[], tenant_id="",
            assessed_at=NOW,
        )
    with pytest.raises(ValueError, match="unbounded"):
        run([{}] * 101)
    with pytest.raises(ValueError, match="untrusted"):
        run([{"prediction": {}, "feedback": {}, "untrusted": "x"}])
    with pytest.raises(ValueError, match="timezone"):
        review_construction_prediction_cohort(
            source_snapshots=snapshots(), pairs=[], tenant_id=TENANT,
            assessed_at=datetime(2026, 10, 14),
        )


def test_operator_cli_live_shape_with_no_predictions_fails_closed(tmp_path, capsys):
    import json
    from scripts.review_construction_predictive_evidence import main

    a, b = tmp_path / "source1.json", tmp_path / "source2.json"
    s = snapshots()
    a.write_text(json.dumps(s[0]), encoding="utf-8")
    b.write_text(json.dumps(s[1]), encoding="utf-8")
    rc = main([
        "--snapshots", str(a), str(b),
        "--tenant-id", "tenant-A",
    ])
    assert rc == 2
    result = json.loads(capsys.readouterr().out)
    assert result["reviewed_prediction_count"] == 0
    assert result["review_status"] == "HOLD"
    assert result["predictive_marketing_claim_ready"] is False
    assert result["actual_revenue_created"] is False
    assert result["execution_authority"] == "NONE"


def test_operator_pairs_read_refuses_symlinks_and_invalid_json(tmp_path):
    from scripts.review_construction_predictive_evidence import read_pairs
    f = tmp_path / "canonical.json"
    f.write_text('{"not":"an array"}', encoding="utf-8")
    with pytest.raises(ValueError, match="list"):
        read_pairs(f)
    f.write_text("[]", encoding="utf-8")
    assert read_pairs(f) == []
    link = tmp_path / "link.json"
    link.symlink_to(f)
    with pytest.raises(ValueError, match="link"):
        read_pairs(link)


def test_operator_malformed_file_does_not_disclose_secret_content(tmp_path, capsys):
    from scripts.review_construction_predictive_evidence import main
    f = tmp_path / "sneaky.json"
    f.write_text('{"private":"SECRET_IN_FILE"}', encoding="utf-8")
    assert main([
        "--snapshots", str(f), str(f), "--tenant-id", "tenant-A",
    ]) == 2
    message = capsys.readouterr().out
    assert "SECRET_IN_FILE" not in message
    assert "execution_authority" in message
