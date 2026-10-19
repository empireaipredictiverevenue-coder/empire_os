"""Scientific data-pathway joins: exact identities, time order, no invented sales."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.opportunity_evidence_router import ROUTES
from empire_os.opportunity_factory_intake import SCORE_KEYS
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED
from empire_os.revenue_evidence_pathways import (
    SOURCES, PathwayEvidenceHold, review_evidence_pathways,
    review_evidence_pathways_runtime,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
KEY = "market:solar:uk"
BLOCKERS = ("buyer_intent_normalized_score_required",
            "margin_potential_normalized_score_required")


def payloads(*, n=1):
    at = (NOW - timedelta(minutes=10)).isoformat()
    sources = {}
    for name, (_, schema) in SOURCES.items():
        sources[name] = {
            "schema_version": schema, "mode": "OBSERVE",
            "generated_at": at, "execution_authority": "none",
            "candidates" if name == "radar" else "items": [],
        }
    for i in range(n):
        key = KEY if i == 0 else f"market:hvac:usa:{i}"
        radar = {
            "opportunity_key": key, "niche": "solar" if i == 0 else "hvac",
            "execution_authority": "none", "revenue_inferred": False,
            "buyer_intent_inferred": False, "commercial_demand_observed": False,
            "source": "market_public_research",
            "raw_private_email": "hidden@example.com",
        }
        intake = {
            "opportunity_key": key, "tenant_id": None,
            "execution_authority": "none", "factory_ready": False,
            "blockers": list(BLOCKERS),
            "normalized_scores": {k:None for k in SCORE_KEYS},
            "revenue_verified": False,
            "evidence_refs": ["source:1"],
            "commercial_contact": "someone@example.net",
        }
        router = {
            "opportunity_key": key, "tenant_id": None,
            "execution_authority": "none",
            "route_count": len(BLOCKERS),
            "routes": [dict(ROUTES[k],blocker=k) for k in BLOCKERS],
        }
        quant = {
            "opportunity_key": key, "tenant_id": None,
            "execution_authority": "none", "factory_ready": False,
            "prediction_ref": None,
            "decision_packet": {
                "status":"UNAVAILABLE",
                "candidate_id":key,
                "execution_authority":"none",
                "actual_revenue":False,
                "missing_fields":list(_DECISION_PACKET_REQUIRED),
            },
        }
        for name,row in (
            ("radar",radar),("intake",intake),
            ("router",router),("quant",quant)
        ):
            sources[name]["candidates" if name=="radar" else "items"].append(row)
    for name in ("intake","quant"):
        sources[name]["candidate_count"] = n
    sources["router"]["opportunity_count"] = n
    return sources


def test_pathway_graph_links_real_stages_without_inventing_probability():
    report = review_evidence_pathways(payloads(),as_of=NOW)
    assert report["status"] == "EVIDENCE_PATHWAY_REVIEW_READY"
    assert report["source_snapshot_count"] == 4
    assert report["candidate_count"] == 1
    assert report["quant_complete_count"] == 0
    assert report["economic_memory_updated"] is False
    assert report["causal_inference_performed"] is False
    assert report["model_weights_updated"] is False
    assert report["all_candidates_are_verified_sales"] is False
    item = report["research_shortlist"][0]
    assert item["niche"] == "solar"
    assert item["first_unverified_requirement"] == BLOCKERS[0]
    assert item["next_owner"] == "business_development"
    assert item["missing_quant_factor_count"] == len(_DECISION_PACKET_REQUIRED)
    assert item["posterior_probability"] is None
    assert item["research_triage_rank_is_revenue_probability"] is False
    assert len(item["pathway_nodes"]) == 5
    assert len(item["pathway_edges"]) == 4
    assert item["pathway_edges"][-1]["evidence_connection"] == "UNVERIFIED_OUTCOME"
    assert all(edge["usable_for_model_training"] is False for edge in item["pathway_edges"])
    assert "someone@example.net" not in json.dumps(report)
    assert "hidden@example.com" not in json.dumps(report)
    assert KEY not in json.dumps(report)


@pytest.mark.parametrize("mutate,reason", [
    (lambda r: r["quant"]["items"][0].update(opportunity_key="other"),
     "cross_stage_identity_join_mismatch"),
    (lambda r: r["quant"]["items"][0].update(tenant_id="private"),
     "quant_tenant_or_row_authority"),
    (lambda r: r["router"]["items"][0]["routes"].clear(),
     "router_count_mismatch"),
    (lambda r: r["quant"]["items"][0].update(prediction_ref="fake"),
     "unavailable_quant_packet_has_prediction_reference"),
    (lambda r: r["intake"]["items"][0].update(factory_ready=True),
     "quant_factory_readiness_contradiction"),
    (lambda r: r["intake"]["items"][0]["normalized_scores"].update(buyer_intent=1.4),
     "invalid_normalized_score"),
    (lambda r: r["router"]["items"][0]["routes"][0].update(action="send_email"),
     "untrusted_routing_authority"),
    (lambda r: r["quant"].update(candidate_count=42),
     "quant_row_count_mismatch"),
    (lambda r: r["radar"]["candidates"].append(deepcopy(r["radar"]["candidates"][0])),
     "radar_duplicate_identity"),
    (lambda r: r["radar"].update(generated_at=(NOW+timedelta(minutes=2)).isoformat()),
     "radar_source_stale_or_future"),
    (lambda r: r["quant"].update(generated_at=(NOW-timedelta(hours=3)).isoformat()),
     "source_snapshot_skew_hold"),
    (lambda r: r["radar"]["candidates"][0].update(revenue_inferred=True),
     "unverified_revenue_or_buyer_claim"),
])
def test_inconsistent_cross_department_evidence_fails_closed(mutate,reason):
    rows=payloads()
    mutate(rows)
    with pytest.raises(PathwayEvidenceHold,match=reason):
        review_evidence_pathways(rows,as_of=NOW)


def test_independently_claimed_demand_without_buyer_evidence_flagged():
    rows=payloads()
    rows["radar"]["candidates"][0]["commercial_demand_observed"]=True
    report=review_evidence_pathways(rows,as_of=NOW)
    item=report["research_shortlist"][0]
    assert report["candidates_with_contradictions"]==1
    assert "demand_claim_without_buyer_intent_evidence" in item["contradictions_to_investigate"]
    assert item["buyer_or_contract_verified"] is False
    assert report["buyer_acceptance_verified"] is False


def test_missing_source_file_holds_entire_graph_without_partial_market_claim(tmp_path):
    result=review_evidence_pathways_runtime(tmp_path,as_of=NOW)
    assert result["status"] == "EVIDENCE_PATHWAY_SOURCE_HOLD"
    assert result["candidate_count"] is None
    assert result["quant_complete_count"] is None
    assert result["scientific_claims_withheld"] is True


def test_pathway_runtime_reads_bounded_canonical_files_without_mutation(tmp_path):
    rows=payloads(n=3)
    original={}
    for name,(rel,_) in SOURCES.items():
        path=tmp_path/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        raw=json.dumps(rows[name]).encode()
        path.write_bytes(raw)
        original[rel]=raw
    result=review_evidence_pathways_runtime(tmp_path,as_of=NOW,limit=2)
    assert result["candidate_count"]==3
    assert len(result["research_shortlist"])==2
    assert result["shortlist_only"] is True
    assert result["source_join_exact_identity_enforced"] is True
    assert all((tmp_path/rel).read_bytes()==original[rel] for rel in original)
    assert result["execution_authority"]=="none"


def test_runtime_cannot_follow_symlink_to_private_source(tmp_path):
    rows=payloads()
    for name,(rel,_) in SOURCES.items():
        path=tmp_path/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(rows[name]))
    (tmp_path/SOURCES["quant"][0]).unlink()
    target=tmp_path/SOURCES["intake"][0]
    (tmp_path/SOURCES["quant"][0]).symlink_to(target)
    result=review_evidence_pathways_runtime(tmp_path,as_of=NOW)
    assert result["status"]=="EVIDENCE_PATHWAY_SOURCE_HOLD"
    assert result["reason_code"]=="unsafe_source_path"


def test_empty_consistent_inventory_does_not_invent_buyers():
    report=review_evidence_pathways(payloads(n=0),as_of=NOW)
    assert report["candidate_count"]==0
    assert report["quant_complete_count"]==0
    assert report["research_shortlist"]==[]
    assert report["buyer_acceptance_verified"] is False
