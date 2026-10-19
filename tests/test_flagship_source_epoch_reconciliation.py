"""Typed source epoch diagnostics use only synthetic canonical source data."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from empire_os.flagship_source_epoch_reconciliation import (
    review_source_epoch_reconciliation,
    review_source_epoch_reconciliation_runtime,
)
from empire_os.revenue_evidence_pathways import (
    SOURCES, PathwayEvidenceHold,
)
from test_revenue_evidence_pathways import payloads, NOW


def review(data):
    return review_source_epoch_reconciliation(data, as_of=NOW)


def test_exact_source_join_reuses_existing_evidence_contract():
    result = review(payloads(n=2))
    assert result["status"] == "FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED"
    assert result["join_result"] == "CANONICAL_PATHWAY_REVIEW_READY"
    assert result["source_counts"] == dict.fromkeys(SOURCES, 2)
    assert result["next_action"] == "RESUME_EXISTING_FIRST_PARTY_BUYER_EVIDENCE_REVIEW"
    assert result["first_party_buyer_verified"] is False
    assert result["conversion_probability_verified"] is False
    assert result["database_writes"] is False


def test_radar_only_additions_provide_precise_owner_recovery_not_partial_forecast():
    sources = payloads(n=3)
    for stage in ("intake", "router", "quant"):
        sources[stage]["items"] = sources[stage]["items"][:2]
        count_key = "opportunity_count" if stage == "router" else "candidate_count"
        sources[stage][count_key] = 2
    result = review(sources)
    assert result["status"] == "RADAR_AHEAD_OF_FACTORY_STAGES"
    assert result["source_counts"] == dict(radar=3, intake=2, router=2, quant=2)
    assert result["radar_missing_from_downstream_counts"] == {
        "intake": 1, "router": 1, "quant": 1,
    }
    assert result["downstream_without_radar_counts"] == {
        "intake": 0, "router": 0, "quant": 0,
    }
    assert result["downstream_three_stage_identities_agree"] is True
    assert result["next_action"] == (
        "REGENERATE_EXISTING_INTAKE_ROUTER_QUANT_FROM_CURRENT_RADAR"
    )
    assert result["join_result"] == "NOT_PROVEN"
    assert result["forecast_issued"] is False
    assert result["outbound_sent"] is False
    serialized = json.dumps(result)
    assert "hidden@example.com" not in serialized
    assert "market:hvac:usa:2" not in serialized
    assert "someone@example.net" not in serialized


def test_dropped_community_candidates_are_not_promoted_or_disclosed():
    sources = payloads(n=3)
    # The standalone Radar source lost an earlier community-pain entry.
    sources["radar"]["candidates"].pop()
    sources["intake"]["items"][-1]["opportunity_class"] = "community_pain"
    sources["intake"]["items"][-1]["niche"] = None
    sources["intake"]["items"][-1]["private_customer_email"] = "do-not-disclose@example.com"
    sources["radar"]["source_status"] = {
        "community_intent": {"available": True, "candidate_count": 0}
    }
    result = review(sources)
    assert result["status"] == "COMMUNITY_SOURCE_POPULATION_CHANGED"
    assert result["next_action"] == "REVIEW_COMMUNITY_INTENT_SOURCE_THEN_RECONCILE_FACTORY_EPOCH"
    assert result["downstream_without_radar_counts"]["intake"] == 1
    assert result["downstream_only_opportunity_class_buckets"] == {"community_pain": 1}
    assert result["downstream_only_missing_niche_count"] == 1
    assert result["radar_community_intent_source_available"] is True
    assert result["radar_community_intent_contribution_count"] == 0
    assert result["join_result"] == "NOT_PROVEN"
    assert "do-not-disclose@example.com" not in json.dumps(result)
    assert result["forecast_issued"] is False


def test_unrelated_downstream_identity_is_drift_not_fresh_radar():
    sources = payloads(n=2)
    sources["quant"]["items"][0]["opportunity_key"] = "different-key"
    result = review(sources)
    assert result["status"] == "MULTI_STAGE_IDENTITY_DRIFT"
    assert result["radar_missing_from_downstream_counts"]["quant"] == 1
    assert result["downstream_without_radar_counts"]["quant"] == 1
    assert result["downstream_three_stage_identities_agree"] is False


def test_identical_keys_with_corrupt_accepted_terms_still_held():
    sources = payloads()
    sources["router"]["items"][0]["routes"][0]["action"] = "send_email"
    result = review(sources)
    assert result["status"] == "CANONICAL_EVIDENCE_CONTRACT_HOLD"
    assert result["canonical_pathway_reason"] == "untrusted_routing_authority"
    assert result["join_result"] == "NOT_PROVEN"
    assert result["forecast_issued"] is False


def test_source_epoch_skew_is_held_before_join_classification():
    sources = payloads()
    sources["radar"]["generated_at"] = (NOW-timedelta(hours=4)).isoformat()
    report = review(sources)
    assert report["status"] == "EPOCH_SKEW_HOLD"
    assert report["next_action"] == "REVIEW_UPSTREAM_SOURCE_EPOCH_SKEW"


@pytest.mark.parametrize("stage", list(SOURCES))
def test_source_stale_future_or_tenant_scoped_fails_closed(stage):
    sources = payloads()
    sources[stage]["generated_at"] = (NOW+timedelta(seconds=1)).isoformat()
    with pytest.raises(PathwayEvidenceHold):
        review(sources)
    sources = payloads()
    source_key = "candidates" if stage=="radar" else "items"
    sources[stage][source_key][0]["tenant_id"] = "private-tenant"
    with pytest.raises(PathwayEvidenceHold):
        review(sources)


def test_runtime_missing_or_unsafe_source_discloses_no_rows(tmp_path):
    report = review_source_epoch_reconciliation_runtime(tmp_path, as_of=NOW)
    assert report["status"] == "SOURCE_UNAVAILABLE"
    assert all(x is None for x in report["source_counts"].values())
    for name,(rel,_) in SOURCES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads()[name]))
    path = tmp_path / SOURCES["quant"][0]
    path.unlink()
    path.symlink_to(tmp_path / SOURCES["router"][0])
    report = review_source_epoch_reconciliation_runtime(tmp_path, as_of=NOW)
    assert report["status"] == "SOURCE_UNAVAILABLE"


def test_runtime_original_source_bytes_unchanged(tmp_path):
    sources=payloads(n=3)
    original={}
    for stage,(rel,_) in SOURCES.items():
        path=tmp_path/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        value=json.dumps(sources[stage])
        path.write_text(value)
        original[rel]=value
    result = review_source_epoch_reconciliation_runtime(tmp_path, as_of=NOW)
    assert result["status"] == "FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED"
    assert all((tmp_path/rel).read_text()==value for rel,value in original.items())
    assert not (tmp_path/"runtime/departments").exists()


def test_existing_owner_handoff_surfaces_epoch_recovery(tmp_path):
    from empire_os.flagship_first_payer_owner_handoff import review_current_first_payer_owner_handoff
    from test_revenue_buyer_evidence_handoff import fixture
    now = fixture(tmp_path)
    path = tmp_path / SOURCES['radar'][0]
    data = json.loads(path.read_text())
    row = deepcopy(data['candidates'][0])
    row['opportunity_key'] = 'fixture:radar:added'
    data['candidates'].append(row)
    path.write_text(json.dumps(data))
    result = review_current_first_payer_owner_handoff(tmp_path, as_of=now)
    assert result['status'] == 'CURRENT_OPPORTUNITY_NOT_ESTABLISHED'
    assert result['first_priority_owner'] == 'existing_opportunity_factory_owner'
    assert result['source_epoch_reconciliation']['status'] == 'RADAR_AHEAD_OF_FACTORY_STAGES'
    assert result['opaque_opportunity_ref'] is None
    assert result['existing_work_item_created'] is False


def test_owner_routes_current_community_epoch_hold_to_existing_factory(tmp_path):
    from empire_os.flagship_first_payer_owner_handoff import review_current_first_payer_owner_handoff
    from test_revenue_buyer_evidence_handoff import fixture
    now = fixture(tmp_path)
    radar_path = tmp_path / SOURCES['radar'][0]
    radar = json.loads(radar_path.read_text())
    radar['candidates'].pop()
    radar['source_status'] = {'community_intent': {'available': True, 'candidate_count': 0}}
    radar_path.write_text(json.dumps(radar))
    intake_path = tmp_path / SOURCES['intake'][0]
    intake = json.loads(intake_path.read_text())
    intake['items'][-1]['opportunity_class'] = 'community_pain'
    intake['items'][-1]['niche'] = None
    intake_path.write_text(json.dumps(intake))
    result = review_current_first_payer_owner_handoff(tmp_path, as_of=now)
    assert result['status'] == 'CURRENT_OPPORTUNITY_NOT_ESTABLISHED'
    assert result['first_priority_owner'] == 'existing_opportunity_factory_owner'
    assert result['first_priority_action'] == 'REVIEW_COMMUNITY_INTENT_SOURCE_THEN_RECONCILE_FACTORY_EPOCH'
    assert result['source_epoch_reconciliation']['status'] == 'COMMUNITY_SOURCE_POPULATION_CHANGED'
    assert result['opaque_opportunity_ref'] is None
    assert result['forecast_issued'] is False
