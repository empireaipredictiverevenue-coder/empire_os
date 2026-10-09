"""Research-review packet bridge contract: deduped, no implicit execution."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from empire_os.system_improvement_review import (
    OUTPUT, MANIFEST, RESOLUTION, RESEARCH_DIR,
    build_review_packets, refresh_review_packets,
)


NOW = datetime(2026, 10, 9, 12, 30, tzinfo=timezone.utc)


def _resolution():
    return {
        "schema": "empire.opportunity_evidence_resolution_shadow.v1",
        "execution_authority": "none", "normalized_scores_written": 0,
        "factory_promotion_authorized": False,
        "items": [
            {
                "opportunity_key": "opp_1",
                "requirements": [
                    {"claim_type": "buyer_intent",
                     "source_capability": "conversation_os",
                     "evidence_state": "NO_CLAIM_SPECIFIC_EVIDENCE",
                     "allowed_source_kinds": ["canonical_verified_reply"],
                     "verified_normalized_score": None},
                    {"claim_type": "demand",
                     "source_capability": "market_gps_and_commercial_outcomes",
                     "evidence_state": "NO_CLAIM_SPECIFIC_EVIDENCE",
                     "verified_normalized_score": None},
                ],
            },
            {
                "opportunity_key": "opp_2",
                "requirements": [
                    {"claim_type": "buyer_intent",
                     "source_capability": "conversation_os",
                     "evidence_state": "NO_CLAIM_SPECIFIC_EVIDENCE",
                     "verified_normalized_score": None},
                    {"claim_type": "demand",
                     "source_capability": "market_gps_and_commercial_outcomes",
                     "evidence_state": "NO_CLAIM_SPECIFIC_EVIDENCE",
                     "verified_normalized_score": None},
                ],
            },
        ],
    }


def _dossier():
    return {
        "workstream": "opportunity_factory",
        "execution_authority": "none",
        "status": "ORIGINAL_SOURCES_CHECKED_REVIEW_REQUIRED",
        "audit": {
            "owner": "data_quant", "checklist_pending": 8,
            "module_examples": ["empire_os/opportunity_loop.py"],
            "related_tests_discovered": ["tests/test_opportunity_loop.py"],
        },
        "upgrade_hypotheses": ["Prove canonical evidence contracts"],
        "citations_to_inspect": [
            {"url": "https://www.nist.gov/itl/ai-risk-management-framework",
             "retrieved_page_verified": True},
            {"url": "https://www.w3.org/TR/prov-o/",
             "retrieved_page_verified": True},
            {"url": "https://someblog.example/test",
             "retrieved_page_verified": False},
        ],
    }


def _write(root: Path, relative: Path | str, value: dict):
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value))


def test_two_opportunities_become_two_claim_tasks_plus_one_review(tmp_path):
    result = build_review_packets(
        tmp_path, resolution=_resolution(),
        dossiers={"opportunity_factory": _dossier()}, now=NOW,
    )
    assert result["task_count"] == 3
    assert result["claim_source_task_count"] == 2
    claim = next(x for x in result["review_packets"]
                 if x.get("claim_type") == "buyer_intent")
    assert claim["affected_opportunity_count"] == 2
    assert claim["target_capability"] == "conversation_os"
    assert "cross_tenant" in claim["verification_contract"]["negative_tests"]
    assert claim["approved_for_implementation"] is False
    assert claim["auto_dispatch_eligible"] is False
    assert claim["write_to_department_work_queue"] is False
    assert claim["allow_payment"] is False
    assert claim["execution_authority"] == "none"
    research = next(x for x in result["review_packets"]
                    if x["task_type"] == "SOURCE_BACKED_ENGINEERING_REVIEW")
    assert len(research["inspected_primary_source_urls"]) == 2
    assert research["local_test_execution_proved_by_research"] is False


def test_packet_materialization_is_idempotent_and_does_not_create_department_queue(tmp_path):
    _write(tmp_path, RESOLUTION, _resolution())
    _write(tmp_path, RESEARCH_DIR / "dossiers/opportunity_factory.json", _dossier())
    first = refresh_review_packets(tmp_path)
    second = refresh_review_packets(tmp_path)
    assert first["task_count"] == second["task_count"] == 3
    assert first["new_or_changed_review_packets"] == 3
    assert second["new_or_changed_review_packets"] == 0
    assert second["unchanged_review_packets"] == 3
    assert len(list((tmp_path / OUTPUT / "pending").glob("*.json"))) == 3
    assert (tmp_path / MANIFEST).exists()
    assert not (tmp_path / "runtime/departments/work/ready").exists()
    assert second["department_work_queue_mutated"] is False


def test_reject_fake_score_or_bypassed_factory_gate(tmp_path):
    evidence = _resolution()
    evidence["normalized_scores_written"] = 1
    with pytest.raises(ValueError, match="unsafe"):
        build_review_packets(tmp_path, resolution=evidence, dossiers={}, now=NOW)
    evidence = _resolution()
    evidence["items"][0]["requirements"][0]["verified_normalized_score"] = 0.99
    with pytest.raises(ValueError, match="promote"):
        build_review_packets(tmp_path, resolution=evidence, dossiers={}, now=NOW)
    evidence = _resolution()
    evidence["factory_promotion_authorized"] = True
    with pytest.raises(ValueError, match="unsafe"):
        build_review_packets(tmp_path, resolution=evidence, dossiers={}, now=NOW)


def test_unreviewed_dossier_never_generates_implementation_task(tmp_path):
    dossier = _dossier()
    dossier["status"] = "RESEARCH_INCOMPLETE"
    result = build_review_packets(
        tmp_path, resolution=_resolution(),
        dossiers={"opportunity_factory": dossier}, now=NOW,
    )
    assert result["source_backed_engineering_review_count"] == 0
    assert result["claim_source_task_count"] == 2


def test_real_observer_is_existence_only_not_buyer_proof(tmp_path):
    rel = "runtime/conversations_replies_control/passive_reply_db_observer_latest.json"
    _write(tmp_path, rel, {
        "generated_at": "2026-10-09T12:00:00+00:00",
        "candidate_count": 0,
        "status": "NO_CANONICAL_REPLY_ROWS",
    })
    result = build_review_packets(tmp_path, resolution=_resolution(),
                                  dossiers={}, now=NOW)
    claim = next(x for x in result["review_packets"]
                 if x.get("claim_type") == "buyer_intent")
    observed = claim["existing_source_observers"][0]
    assert observed["artifact_present"] is True
    assert observed["freshness"] == "OBSERVED_WITHIN_7_DAYS"
    assert observed["canonical_business_proof_verified"] is False
    assert observed["source_is_authenticated_event_stream"] is False


def test_human_review_state_is_not_overwritten(tmp_path):
    _write(tmp_path, RESOLUTION, _resolution())
    _write(tmp_path, RESEARCH_DIR / "dossiers/opportunity_factory.json", _dossier())
    initial = refresh_review_packets(tmp_path)
    packet_path = tmp_path / initial["packets"][0]["path"]
    packet = json.loads(packet_path.read_text())
    packet["state"] = "APPROVED_BY_FOUNDER"
    packet["approved_for_implementation"] = True
    packet_path.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="external state"):
        refresh_review_packets(tmp_path)
    assert json.loads(packet_path.read_text())["state"] == "APPROVED_BY_FOUNDER"
    assert not (tmp_path / "runtime/departments/work/ready").exists()


def test_prioritised_board_exposes_exact_source_gaps_without_business_proof(tmp_path):
    _write(tmp_path, RESOLUTION, _resolution())
    _write(tmp_path, RESEARCH_DIR / "dossiers/opportunity_factory.json", _dossier())
    result = refresh_review_packets(tmp_path)
    board = (tmp_path / OUTPUT / "latest.md").read_text()
    assert result["task_count"] == 3
    assert "Evidence & Research Improvement Board" in board
    assert "buyer_intent" in board
    assert "market_gps_and_commercial_outcomes" in board
    assert "authenticated commercial proof" in board
    assert "automatic execution" in board
    assert "opp_1" not in board and "opp_2" not in board
