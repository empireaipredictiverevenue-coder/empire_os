"""Passive cross-department hooks reuse the existing cycle without dispatch."""
from __future__ import annotations
from pathlib import Path

import empire_os.department_cycle as module


def test_scratch_root_does_not_query_production():
    result=module.review_revenue_first_hooks_in_cycle(Path("/tmp/another-worktree"))
    assert result["status"] == "NOT_CANONICAL_RUNTIME"
    assert result["hooks_dispatched"] == 0
    assert result["execution_authority"] == "none"


def test_canonical_cycle_includes_read_only_prioritised_hooks(monkeypatch,tmp_path):
    from scripts import review_revenue_first_hook_evidence as reader
    monkeypatch.setattr(module,"CANONICAL_HOOK_REVIEW_ROOT",tmp_path)
    monkeypatch.setattr(reader,"run",lambda **kw:{
        "candidate_count": 2,
        "existing_hook_candidates": [
            {"hook_key":"buyer_reply_evidence_review","priority":98,"review_status":"EVIDENCE_REVIEW_PENDING"},
            {"hook_key":"seo_source_integrity_review","priority":94,"review_status":"EVIDENCE_REVIEW_PENDING"},
        ],
        "source_status":{
            "search_intelligence":{"interpretation":"MEASUREMENT_EVIDENCE_INCOMPLETE"},
            "buyer_replies":{"interpretation":"NO_CANONICAL_BUYER_REPLY_PROOF"},
            "conversion":{"interpretation":"BUYER_REPLY_STAGE_BOTTLENECK"},
            "revenue_pulse":{"interpretation":"RECOGNIZED_REVENUE_ZERO_IN_SNAPSHOT"},
        },
        "jobs_dispatched":0,"models_invoked":0,"buyer_replies_sent":0,"payments_executed":0,
    })
    result=module.review_revenue_first_hooks_in_cycle(tmp_path)
    assert result["status"]=="REVIEW_ONLY_NO_DISPATCH"
    assert result["candidate_count"]==2
    assert result["hooks_dispatched"]==0
    assert result["outbound_sent"]==0
    assert result["payments_executed"]==0
    assert result["seo_evidence_state"]=="MEASUREMENT_EVIDENCE_INCOMPLETE"
    assert result["buyer_reply_evidence_state"]=="NO_CANONICAL_BUYER_REPLY_PROOF"
    assert [v["priority"] for v in result["candidates"]]==[98,94]


def test_unavailable_source_does_not_break_other_cycle_steps(monkeypatch,tmp_path):
    from scripts import review_revenue_first_hook_evidence as reader
    monkeypatch.setattr(module,"CANONICAL_HOOK_REVIEW_ROOT",tmp_path)
    monkeypatch.setattr(reader,"run",lambda **kw:(_ for _ in ()).throw(OSError("private hidden details")))
    result=module.review_revenue_first_hooks_in_cycle(tmp_path)
    assert result["status"]=="HELD_SOURCE_UNAVAILABLE"
    assert result["reason_code"]=="OSError"
    assert result["candidate_count"]==0
    assert result["hooks_dispatched"]==0
    assert "private hidden details" not in str(result)
