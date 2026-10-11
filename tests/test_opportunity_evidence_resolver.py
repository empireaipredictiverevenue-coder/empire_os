"""Claim-specific resolver must reject public proxies, stale/foreign evidence."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from empire_os.opportunity_evidence_resolver import (
    claim_for, check_candidate, resolve, refresh, source_integrity,
)


def sample():
    route = {"items": [{"opportunity_key": "q1", "opportunity_class": "market_research",
                        "routes": [{"blocker": c + "_normalized_score_required",
                                    "capability": "canonical"} for c in (
                                        "buyer_intent", "demand", "urgency",
                                        "data_advantage", "fulfilment_readiness"
                                    )]}]}
    radar = {"candidates": [{"opportunity_key": "q1", "tenant_id": "t1"}]}
    return route, radar


def test_21_opportunities_generate_precise_tasks_no_scores(tmp_path):
    routes, radar = sample()
    routes["items"] = [{**routes["items"][0], "opportunity_key": "q" + str(i)}
                       for i in range(21)]
    radar["candidates"] = [
        {"opportunity_key": "q" + str(i), "tenant_id": "t1"}
        for i in range(21)
    ]
    result = resolve(tmp_path, routes=routes, radar=radar, attestations={})
    assert result["opportunities"] == 21
    assert result["unresolved_requirements"] == 105
    assert result["reason_counts"] == {"NO_CLAIM_SPECIFIC_EVIDENCE": 105}
    assert result["normalized_scores_written"] == 0
    assert result["factory_promotion_authorized"] is False
    assert all(
        proof["verified_normalized_score"] is None
        for item in result["items"] for proof in item["requirements"]
    )


def attestation(root: Path, *, now: datetime):
    p = root / "runtime/conversations_replies_control/proof.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"source_event_id": "r1", "tenant_id": "t1"}))
    return {
        "opportunity_key": "q1", "tenant_id": "t1",
        "claim_type": "buyer_intent",
        "source_kind": "canonical_verified_reply",
        "source_event_id": "r1",
        "source_artifact": "runtime/conversations_replies_control/proof.json",
        "source_sha256": sha256(p.read_bytes()).hexdigest(),
        "source_event_at": now.isoformat(),
        "captured_at": now.isoformat(),
        "verification_status": "VERIFIED_SOURCE_EVENT",
        "ai_generated": False,
    }


@pytest.mark.parametrize("fault,expected", [
    ({"tenant_id": "t2"}, "TENANT_SCOPE_MISMATCH"),
    ({"source_kind": "public_search"}, "SOURCE_TYPE_NOT_ADMISSIBLE"),
    ({"ai_generated": True}, "MODEL_ASSERTION_NOT_EVIDENCE"),
    ({"verification_status": "AI_MODEL_ASSERTED"}, "SOURCE_VERIFICATION_NOT_PROVED"),
    ({"source_sha256": "f"*64}, "SOURCE_DIGEST_MISMATCH"),
    ({"source_artifact": "../../etc/passwd"}, "UNTRUSTED_SOURCE_PATH"),
    ({"source_event_id": ""}, "CANONICAL_EVENT_ID_REQUIRED"),
])
def test_negative_attestation_gates(tmp_path, fault, expected):
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    proof = attestation(tmp_path, now=now)
    proof.update(fault)
    r = check_candidate(tmp_path, {"opportunity_key": "q1", "tenant_id": "t1"},
                        "buyer_intent", proof, now)
    assert r == expected


def test_stale_and_unscoped_proofs_fail_closed(tmp_path):
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    proof = attestation(tmp_path, now=now)
    proof["source_event_at"] = (now - timedelta(days=16)).isoformat()
    assert check_candidate(tmp_path, {"opportunity_key": "q1", "tenant_id": "t1"},
                           "buyer_intent", proof, now) == "SOURCE_STALE_FOR_CLAIM"
    proof = attestation(tmp_path, now=now)
    assert check_candidate(tmp_path, {"opportunity_key": "q1"},
                           "buyer_intent", proof, now) == "OPPORTUNITY_TENANT_UNRESOLVED"


def test_hash_matched_source_still_requires_authenticity_review(tmp_path):
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    proof = attestation(tmp_path, now=now)
    assert source_integrity(tmp_path, proof) == "CONTENT_HASH_MATCH_NOT_AUTHENTICATED"
    routes, radar = sample()
    result = resolve(tmp_path, routes=routes, radar=radar,
                     attestations={"attestations": [proof]}, now=now)
    assert result["content_hash_matches_needing_authenticity_review"] == 1
    assert result["reason_counts"]["SOURCE_MATCHED_AUTHENTICITY_REVIEW_REQUIRED"] == 1
    assert result["normalized_scores_written"] == 0
    assert result["factory_promotion_authorized"] is False
    assert result["commercial_facts_auto_verified"] == 0


def test_read_only_input_materialization_never_modifies_originals(tmp_path):
    routes, radar = sample()
    paths = [
        ("runtime/opportunity_factory/evidence_routes_latest.json", routes),
        ("runtime/opportunity_radar/latest.json", radar),
    ]
    for rel, value in paths:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))
    before = [(tmp_path / p).read_bytes() for p, _ in paths]
    result = refresh(tmp_path)
    after = [(tmp_path / p).read_bytes() for p, _ in paths]
    assert before == after
    assert result["unresolved_requirements"] == 5
    assert (tmp_path / "runtime/opportunity_factory/evidence_resolution_latest.json").exists()
    assert claim_for("buyer_intent_normalized_score_required") == "buyer_intent"


def test_unscoped_opportunity_remains_diagnostic_without_score_promotion(tmp_path):
    routes, radar = sample()
    radar["candidates"][0].pop("tenant_id")
    result = resolve(tmp_path, routes=routes, radar=radar, attestations={},
                     now=datetime(2026, 10, 9, tzinfo=timezone.utc))
    assert result["unscoped_opportunity_count"] == 1
    assert all(
        row["tenant_binding_status"] == "MISSING_TENANT_SCOPE"
        and row["verified_normalized_score"] is None
        for item in result["items"] for row in item["requirements"]
    )
    assert result["commercial_facts_auto_verified"] == 0
    assert result["factory_promotion_authorized"] is False
    assert result["execution_authority"] == "none"
