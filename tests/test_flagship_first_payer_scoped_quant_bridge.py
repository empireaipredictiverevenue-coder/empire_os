"""Exact opportunity first-payer bridge: synthetic owner paths and receipts."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from empire_os.flagship_first_payer_scoped_quant_bridge import (
    review_first_payer_scoped_quant_bridge as bridge,
)
from empire_os.revenue_buyer_evidence_handoff import (
    review_one_commercial_evidence_request,
)
from empire_os.revenue_evidence_pathways import SOURCES
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED
from test_revenue_buyer_evidence_handoff import fixture
from test_flagship_first_payer_quant_preflight import ECONOMICS


def current(tmp_path):
    now = fixture(tmp_path)
    old = review_one_commercial_evidence_request(tmp_path, as_of=now)
    ref = old["request"]["opportunity_ref"]
    radar = json.loads((tmp_path / SOURCES["radar"][0]).read_text())
    key = next(row["opportunity_key"] for row in radar["candidates"]
               if "oppref_"+sha256(row["opportunity_key"].encode()).hexdigest()[:20] == ref)
    return now, ref, key


def review(tmp_path, now, **changes):
    return bridge(tmp_path, as_of=now, **changes)


def test_unknown_owner_scope_stays_explicit_and_no_payer_claim(tmp_path):
    now, ref, key = current(tmp_path)
    outcome = review(tmp_path, now)
    assert outcome["status"] == "SCOPED_SOURCE_IDENTITY_REQUIRED"
    assert outcome["opaque_opportunity_ref"] == ref
    assert outcome["original_source_identity_bound"] is True
    assert outcome["tenant_scope_authenticated"] is False
    assert outcome["source_market_checked_from_current_snapshot"] is True
    assert outcome["buyer_terms_authenticated"] is False
    assert outcome["economic_memory_verified_terminal_pairs"] is None
    assert outcome["original_forecast_registered"] is False
    assert outcome["outbound_sent"] is False
    assert outcome["database_writes"] is False


def test_scoped_original_row_binds_only_market_revision_not_buyer_proof(tmp_path):
    now, _, key = current(tmp_path)
    result = review(tmp_path, now, tenant_id="fixture-tenant",opportunity_key=key,
                    model_name="original_model",model_version="v1",
                    quant_inputs={},source_receipts={})
    assert result["status"] == "SAME_OPPORTUNITY_SCIENTIFIC_REVIEW_HELD"
    assert result["original_source_identity_bound"] is True
    assert result["original_market_revision_bound"] is True
    assert result["source_market_checked_from_current_snapshot"] is True
    assert result["tenant_scope_authenticated"] is False
    assert result["quant_preflight_status"] == "QUANT_EVIDENCE_INCOMPLETE"
    assert result["missing_quant_fields"] == list(_DECISION_PACKET_REQUIRED)
    assert result["buyer_capacity_authenticated"] is False
    assert result["original_source_receipts_authenticated"] is False
    assert result["original_forecast_registered"] is False
    assert "fixture-tenant" not in json.dumps(result)
    assert key not in json.dumps(result)
    assert not (tmp_path/"runtime/departments/work").exists()


def test_mismatched_key_never_borrows_original_buyer_economics(tmp_path):
    now, _, key = current(tmp_path)
    outcome = review(tmp_path, now, tenant_id="fixture-tenant",
                     opportunity_key=key+"-other")
    assert outcome["status"] == "SCOPED_OPPORTUNITY_IDENTITY_MISMATCH"
    assert outcome["original_source_identity_bound"] is False
    assert outcome["quant_preview_checked"] is False


def test_complete_self_declared_quant_receipts_are_still_not_authenticated(tmp_path):
    now, _, key = current(tmp_path)
    originals = {
        factor: {
            "tenant_id": "fixture-tenant",
            "opportunity_key": key,
            "source_ref": "canonical:synthetic:"+factor,
            "observed_at": (now - timedelta(minutes=1)).isoformat(),
            "value": value,
            "source_class": "ORIGINAL_MODEL_OUTPUT" if factor in
                            ("probability_success","confidence","uncertainty")
                            else "FIRST_PARTY_COMMERCIAL",
        } for factor,value in ECONOMICS.items()
    }
    outcome = review(tmp_path, now,tenant_id="fixture-tenant",
                    opportunity_key=key,model_name="existing_quant",
                    model_version="v1",quant_inputs=deepcopy(ECONOMICS),
                    source_receipts=originals)
    assert outcome["status"] == "SAME_OPPORTUNITY_SCIENTIFIC_REVIEW_HELD"
    assert outcome["quant_preflight_status"] == "QUANT_PREVIEW_UNAUTHENTICATED_ORIGINAL_EVIDENCE"
    assert outcome["missing_quant_fields"] == []
    assert outcome["original_model_probability_authenticated"] is False
    assert outcome["original_source_receipts_authenticated"] is False
    assert outcome["buyer_terms_authenticated"] is False
    assert outcome["original_forecast_registered"] is False
    assert outcome["training_or_calibration_performed"] is False


def test_missing_and_wrong_tenant_fields_fail_before_read_or_preview(tmp_path):
    now, _, key = current(tmp_path)
    with pytest.raises(ValueError):
        review(tmp_path, now, tenant_id="fixture-tenant")
    with pytest.raises(ValueError):
        review(tmp_path, now,opportunity_key=key)
    with pytest.raises(ValueError):
        review(tmp_path, now,tenant_id="fixture-tenant",opportunity_key=key,
               quant_inputs={})


def test_invalid_source_receipt_does_not_promote_forecast(tmp_path):
    now, _, key = current(tmp_path)
    bad = {"probability_success": {
        "tenant_id": "another-tenant", "opportunity_key": key,
        "source_ref": "canonical:synthetic:prob",
        "observed_at": now.isoformat(), "value": .7,
        "source_class": "ORIGINAL_MODEL_OUTPUT",
    }}
    with pytest.raises(ValueError,match="another opportunity or tenant"):
        review(tmp_path, now,tenant_id="fixture-tenant",opportunity_key=key,
               model_name="m",model_version="v1",
               quant_inputs={"probability_success": .7},source_receipts=bad)


def test_changed_current_epoch_short_circuits_scoped_join(tmp_path):
    now, _, key = current(tmp_path)
    path=tmp_path / SOURCES["radar"][0]
    radar=json.loads(path.read_text())
    radar["candidates"].pop()
    path.write_text(json.dumps(radar))
    report=review(tmp_path,now,tenant_id="fixture-tenant",opportunity_key=key)
    assert report["status"] == "SOURCE_EPOCH_HOLD"
    assert report["original_source_identity_bound"] is False
    assert report["opaque_opportunity_ref"] is None
    assert report["quant_preview_checked"] is False


def test_unknown_market_only_held_in_owner_and_not_assigned_to_buyer(tmp_path):
    now, _, key = current(tmp_path)
    path = tmp_path / SOURCES["radar"][0]
    radar = json.loads(path.read_text())
    for row in radar["candidates"]:
        if row["opportunity_key"] == key:
            row["niche"] = None
    path.write_text(json.dumps(radar))
    result = review(tmp_path,now,tenant_id="fixture-tenant",opportunity_key=key)
    assert result["status"] == "MARKET_IDENTITY_REQUIRED"
    assert result["original_source_identity_bound"] is False
    assert result["buyer_specific_buybox_authenticated"] is False


def test_unowned_market_research_is_a_buyer_research_task_not_a_tenant(tmp_path):
    now, ref, _ = current(tmp_path)
    path = tmp_path / SOURCES['radar'][0]
    original = json.loads(path.read_text())
    for row in original['candidates']:
        row['source'] = 'market_sweeps_revenue_gps'
        row['opportunity_class'] = 'market_research'
        row['metro'] = ':'.join(row['opportunity_key'].split(':')[2:])
        row['tenant_id'] = None
        row['org_id'] = None
    path.write_text(json.dumps(original))
    result = review(tmp_path, now)
    assert result['status'] == 'UNOWNED_MARKET_RESEARCH_NOT_BUYER'
    assert result['opaque_opportunity_ref'] == ref
    assert result['source_epoch_status'] == 'FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED'
    assert result['source_market_checked_from_current_snapshot'] is True
    assert result['tenant_scope_authenticated'] is False
    assert result['buyer_identity_observed_in_selected_research'] is False
    assert result['next_owner'] == 'business_development'
    assert result['next_action'] == 'VERIFY_FIRST_PARTY_BUYER_INTEREST_TERMS_AND_TENANT_LINK'
    assert result['quant_preview_checked'] is False
    assert result['original_forecast_registered'] is False
    assert result['buyer_terms_authenticated'] is False
    assert result['database_writes'] is False
    serialized=json.dumps(result)
    assert 'market_sweeps_revenue_gps' not in serialized
    assert 'fixture-tenant' not in serialized


def test_source_mutation_never_forges_buyer_or_identity(tmp_path):
    now, _, key = current(tmp_path)
    path=tmp_path / SOURCES['radar'][0]
    original=json.loads(path.read_text())
    for row in original['candidates']:
        if row['opportunity_key'] == key:
            row['source'] = 'market_sweeps_revenue_gps'
            row['opportunity_class'] = 'market_research'
            row['metro'] = 'changed metro'
    path.write_text(json.dumps(original))
    result=review(tmp_path,now)
    assert result['status'] in ('SOURCE_EPOCH_HOLD','SOURCE_REVISION_DRIFT',
                                'NO_CURRENT_FIRST_PAYER_SOURCE')
    assert result['original_forecast_registered'] is False
    assert result['buyer_terms_authenticated'] is False


def test_exact_key_cannot_hide_niche_drift_between_radar_and_intake(tmp_path):
    now, _, key = current(tmp_path)
    target = tmp_path / SOURCES['intake'][0]
    rows = json.loads(target.read_text())
    for row in rows['items']:
        if row['opportunity_key'] == key:
            row['niche'] = 'unrelated-specialty'
    target.write_text(json.dumps(rows))
    result = review(tmp_path, now)
    assert result['status'] == 'SOURCE_REVISION_DRIFT'
    assert result['original_source_identity_bound'] is False
    assert result['buyer_specific_buybox_authenticated'] is False
    assert result['original_forecast_registered'] is False
