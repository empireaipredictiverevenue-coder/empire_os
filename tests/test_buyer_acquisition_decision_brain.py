"""Original Buyer Acquisition Team brain: decisions, fairness and no duplicate jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from empire_os.buyer_acquisition_decision_brain import (
    QUAL, REPORT, STATE, classify, review, run_team_brain, SCHEMA,
)


NOW = datetime(2026, 10, 26, 17, 35, tzinfo=timezone.utc)


def row(i: int, *, action="RESEARCH_COMPANY_ROLE_DEMAND_AND_FIRST_PARTY_CONTACT_PATH",
        tier="EVIDENCE_RECOVERY", contact="DISCOVERED_NO_CONFIRMED_CONTACT",
        sector=False, due="CURRENT"):
    return {
        "domain": f"buyer{i}.com", "commercial_next_action": action,
        "contact_history_state": contact, "tier": tier,
        "buyer_relationship_role_review": "UNCLASSIFIED_BUYER_RESEARCH",
        "first_party_due_diligence": {
            "freshness": due, "observed_at": NOW.isoformat(),
        },
        "active_demand_sector_research_fit": {
            "state": "FIRST_PARTY_SECTOR_RESEARCH_FIT" if sector
            else "NO_SECTOR_GAP_MATCH_OBSERVED",
            "first_party_matching_sector_names": ["roofing"] if sector else [],
            "sample_corridors_for_research": [
                "corridor:v1:roofing:denver_co:qualified_lead:lead"
            ] if sector else [],
            "market_or_zip_coverage_verified": False,
            "observed_overflow_units_for_sectors": 13 if sector else 0,
        },
    }


def snapshot(n: int, *, at=NOW):
    return {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": at.isoformat(),
        "outbound_sent": False, "outbound_enabled": False,
        "targets": [row(i) for i in range(n)],
    }


def test_brain_cycles_all_62_records_once_in_bounded_batches():
    source = snapshot(62)
    previous = None
    all_domains = []
    for cycle in range(4):
        report, previous = review(source, previous, now=NOW+timedelta(minutes=cycle))
        current = [i["domain"] for i in report["priority_worklist"]]
        assert not set(current).intersection(all_domains)
        all_domains.extend(current)
        assert report["outbound_authorized"] is False
        assert report["database_writes"] is False
        assert report["individual_recommendations_dispatched"] is False
        assert previous["outbound_authorized"] is False
        assert len(current) <= 25
    assert len(all_domains) == 62
    assert report["worklist_truncated_count"] == 0
    assert report["materially_changed_recommendations"] == 0
    assert report["unchanged_recommendations_suppressed"] == 62


def test_live_relationship_and_sector_gap_outrank_generic_research():
    rows = [row(i) for i in range(30)]
    rows[7] = row(7, contact="WORKSPACE_RECIPROCAL_THREAD_OBSERVED", tier="FOUNDER_REVIEW_ONLY")
    rows[9] = row(9, tier="FOUNDER_REVIEW_ONLY", sector=True)
    rows[10] = row(10, action="NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY",
                   tier="MANUAL_EVIDENCE_HOLD")
    source = snapshot(0)
    source["targets"] = rows
    result, _ = review(source, None, now=NOW)
    assert result["priority_worklist"][0]["domain"] == "buyer7.com"
    assert result["priority_worklist"][1]["domain"] == "buyer9.com"
    assert "buyer10.com" not in [i["domain"] for i in result["priority_worklist"]]
    assert result["policy_held_count"] == 1
    assert result["recommendation_types"]["REVIEW_EXISTING_BUYER_RELATIONSHIP"] == 1


def test_unchanged_stops_retries_and_proven_change_reopens_only_one():
    source = snapshot(3)
    one, previous = review(source, None, now=NOW)
    two, previous = review(source, previous, now=NOW+timedelta(minutes=5))
    assert not two["priority_worklist"]
    source["targets"][1]["contact_history_state"] = "WORKSPACE_RECIPROCAL_THREAD_OBSERVED"
    three, previous = review(source, previous, now=NOW+timedelta(minutes=10))
    assert [x["domain"] for x in three["priority_worklist"]] == ["buyer1.com"]
    assert three["priority_worklist"][0]["recommended_action"] == (
        "REVIEW_EXISTING_BUYER_RELATIONSHIP")


def test_source_and_existing_checkpoint_must_be_safe():
    source = snapshot(1)
    source["outbound_enabled"] = True
    with pytest.raises(ValueError, match="unsafe_buyer_qualification"):
        review(source, None, now=NOW)
    source["outbound_enabled"] = False
    report, checkpoint = review(source, None, now=NOW)
    assert checkpoint["schema_version"] == SCHEMA
    checkpoint["payment_authorized"] = True
    with pytest.raises(ValueError, match="unsafe_previous"):
        review(source, checkpoint, now=NOW)
    source["generated_at"] = (NOW-timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="stale"):
        review(source, None, now=NOW)


def test_original_team_brain_reuses_existing_refresh_with_cooldown(tmp_path, monkeypatch):
    source = snapshot(3, at=NOW-timedelta(minutes=35))
    p = tmp_path / QUAL
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(source))
    calls = []
    def fake_refresh(cmd, **kwargs):
        calls.append(cmd)
        refreshed = dict(source, generated_at=NOW.isoformat())
        p.write_text(json.dumps(refreshed))
        return SimpleNamespace(returncode=0)
    from empire_os import buyer_acquisition_decision_brain as brain
    monkeypatch.setattr(brain.subprocess, "run", fake_refresh)
    output = run_team_brain(tmp_path, now=NOW)
    assert output["existing_qualification_refresh"] == "EXISTING_QUALIFICATION_REFRESH_SUCCEEDED"
    assert len(calls) == 1
    assert calls[0][-2:] == [
        str(tmp_path/"scripts/build_buyer_qualification_actions.py"), "--write"]
    assert (tmp_path/REPORT).is_file()
    assert (tmp_path/STATE).is_file()
    assert json.loads((tmp_path/REPORT).read_text())["current_candidates"] == 3
    assert run_team_brain(tmp_path, now=NOW+timedelta(minutes=5))[
        "existing_qualification_refresh"] == "NOT_DUE"
    assert len(calls) == 1


def test_failed_refresh_does_not_repeat_each_five_minutes(tmp_path, monkeypatch):
    source = snapshot(2, at=NOW-timedelta(minutes=22))
    p=tmp_path/QUAL
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(source))
    calls=[]
    from empire_os import buyer_acquisition_decision_brain as brain
    def fail(cmd,**kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(brain.subprocess,"run",fail)
    first = run_team_brain(tmp_path,now=NOW)
    assert first["existing_qualification_refresh"] == "EXISTING_INTERNAL_REFRESH_FAILED"
    second=run_team_brain(tmp_path,now=NOW+timedelta(minutes=5))
    assert second["existing_qualification_refresh"] == "NOT_DUE"
    assert len(calls)==1
    assert second["repeat_decisions_suppressed"] == 2


def test_never_treat_dispatched_recommendation_as_contact_or_buyer_acceptance():
    source=snapshot(1)
    source["targets"][0]["contact_history_state"]="FOUNDER_FORM_SUBMITTED"
    report,_=review(source,None,now=NOW)
    job=report["priority_worklist"][0]
    assert job["recommended_action"]=="REVIEW_EXISTING_BUYER_RELATIONSHIP"
    for name in ("market_coverage_verified","buyer_acceptance_verified",
                 "outbound_authorized","task_dispatched"):
        assert job[name] is False
    assert report["external_execution_performed"] is False
