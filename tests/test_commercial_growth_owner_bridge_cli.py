"""Offline subprocess contract test for CLI consuming existing BD stdout."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts.review_commercial_growth_owner_bridge_20261020"


def inputs(tmp_path):
    samples = {
        "observations": {"observations": []},
        "offerbook": {
            "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
            "generated_at": "2026-09-30T00:00:00Z",
            "targets": [{
                "company": "Synthetic Example",
                "canonical_prospect_id": None,
                "state": "PRODUCT_READINESS_REQUIRED",
                "person_verified": False,
                "email_verified": False,
                "demand_state": "UNKNOWN",
                "offer_package_ready": False,
            }],
        },
        "funnel": {
            "schema_version": "empire.founder_commercial_funnel.v1",
            "generated_at": "2026-09-22T00:00:00Z",
        },
    }
    paths = []
    for label, data in samples.items():
        path = tmp_path / (label + ".json")
        path.write_text(json.dumps(data))
        paths.append(str(path))
    return [
        "--read-only",
        "--observations-file", paths[0],
        "--offer-book-file", paths[1],
        "--funnel-file", paths[2],
        "--buyer-development-review-file", "-",
    ]


def bd():
    return {
        "schema_version": "empire.bd.conversion_desk_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "database_writes": False,
        "outbound_allowed": False,
        "status": "BUSINESS_DEVELOPMENT_RESEARCH_TRIAGE_READY",
        "scout_candidate_count": 1,
        "fully_activated_buyer_count": 0,
        "review_ready_count": 0,
        "priority_actions": [],
    }


def test_stdin_contract_produces_only_nonexecuting_combined_review(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", "-m", SCRIPT, *inputs(tmp_path)],
        cwd=ROOT, input=json.dumps(bd()), text=True,
        capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    review = json.loads(result.stdout)
    assert review["status"] == "SOURCE_REVIEW_HOLD"
    assert review["historical_offer_book_cohort"]["historical_offer_target_count"] == 1
    assert review["existing_buyer_development_cohort"]["scout_candidate_count"] == 1
    assert review["agent_tasks_created"] is False
    assert review["outbound_allowed"] is False


def test_reject_untrusted_bd_stdin_without_writing(tmp_path):
    forged = bd()
    forged["outbound_allowed"] = True
    result = subprocess.run(
        [sys.executable, "-B", "-m", SCRIPT, *inputs(tmp_path)],
        cwd=ROOT, input=json.dumps(forged), text=True,
        capture_output=True, timeout=15,
    )
    assert result.returncode != 0
    assert not list(tmp_path.glob("*.tmp"))
