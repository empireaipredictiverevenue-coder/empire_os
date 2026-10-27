"""Verify read-only CRO reuse, missing measurements, and source-copy review."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from empire_os.competitor_call_cro_owner_handoff import build_cro_owner_handoff, PAGE, FORM
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 13, tzinfo=timezone.utc)

def sample():
    return {
        "schema_version": "empire.competitor_call_conversion_readiness.v1",
        "mode": "OBSERVE",
        "exact_source_to_settlement_proven": False,
        "acquisition_source_profitability_calibrated": False,
        "source_registry_available": True,
        "ad_spend_authorized": False,
        "content_publication_authorized": False,
        "external_send_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
        "measurement_chain_steps": [
            {"stage": x, "verified": False, "count": None}
            for x in range(6)
        ],
    }

def test_canonical_conversion_specialist_no_invented_rates():
    x = build_cro_owner_handoff(
        readiness=sample(), page_source=(ROOT / PAGE).read_text(),
        form_source=(ROOT / FORM).read_text(), now=NOW,
    )
    assert x["existing_specialist_reused"] is True
    assert x["original_specialist_stage_count"] == 12
    assert x["original_specialist_unknown_stage_count"] == 12
    assert x["original_specialist_primary_bottleneck"] is None
    assert x["original_specialist_experiment_candidate"] is None
    assert not x["site_changed"] and not x["automated_experiment_approved"]
    assert len(x["proposed_cro_reviews"]) == 5
    src = x["static_candidate_source_review"]
    assert src["traffic_disabled_banner_in_source"]
    assert src["hero_call_request_cta_in_source"]
    assert src["calls_disabled_faq_in_source"]
    assert src["call_handoff_conditional_in_source"]
    assert src["not_live_deployment_attestation"]

def test_missing_source_not_claimed_to_be_live():
    x = build_cro_owner_handoff(readiness=sample(), page_source=None,
                                 form_source=None, now=NOW)
    assert not x["static_candidate_source_review"]["source_available"]
    assert x["original_specialist_primary_bottleneck"] is None

@pytest.mark.parametrize("invalid", ["exact_source_to_settlement_proven",
    "acquisition_source_profitability_calibrated", "ad_spend_authorized",
    "content_publication_authorized", "database_writes"])
def test_mutated_authority_held(invalid):
    s = sample()
    s[invalid] = True
    with pytest.raises(ValueError):
        build_cro_owner_handoff(readiness=s, page_source=None,
                                form_source=None, now=NOW)

def test_original_founder_feed_accepts_only_readonly_cro(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas
    p = tmp_path / "runtime/competitive_intelligence"
    p.mkdir(parents=True)
    raw = json.loads((ROOT / SOURCE).read_text())
    (p / "call_acquisition_atlas_latest.json").write_text(
        json.dumps(build_atlas(raw, now=NOW)))
    (p / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14}')
    x = build_cro_owner_handoff(readiness=sample(),
                                page_source=(ROOT / PAGE).read_text(),
                                form_source=(ROOT / FORM).read_text(), now=NOW)
    (p / "call_cro_owner_handoff_latest.json").write_text(json.dumps(x))
    result = build_feed_runtime(tmp_path)
    assert result["canonical_company_count"] == 14
    overlay = result["call_acquisition_intelligence"]["cro_owner_handoff"]
    assert overlay["available"] is True
    assert overlay["existing_specialist_reused"] is True
    assert overlay["primary_bottleneck"] is None
    x["automated_experiment_approved"] = True
    (p / "call_cro_owner_handoff_latest.json").write_text(json.dumps(x))
    rejected = build_feed_runtime(tmp_path)
    assert rejected["call_acquisition_intelligence"]["cro_owner_handoff"][
        "available"] is False
