"""Existing commercial intelligence owner: pure, evidence-ranked handoff only."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import subprocess
import sys

import pytest

from empire_os.commercial_adaptive_intelligence_control import (
    review_adaptive_commercial_intelligence,
)
from scripts.review_commercial_adaptive_intelligence_20261020 import (
    founder_owner_evidence_handoff,
)
from test_commercial_adaptive_intelligence_control import fixtures
from test_commercial_adaptive_intelligence_cli import _test_sources

def control():
    return review_adaptive_commercial_intelligence(**fixtures(cases=5,suppressed=2))


def test_root_commercial_evidence_is_first_and_downstream_not_repeated():
    source=control()
    before=deepcopy(source)
    result=founder_owner_evidence_handoff(source)
    assert source==before
    assert result["schema_version"]=="empire.commercial.adaptive_founder_handoff.v1"
    assert result["primary_commercial_gate"]=="BUYER_CAPACITY_AND_TERMS"
    assert result["original_owner_handoffs"][0]["existing_owner_lane"]=="commercial_evidence_verifier"
    names={row["gate"]:row for row in result["original_owner_handoffs"]}
    # An authenticated, non-suppressed subcohort may be reviewable even
    # while the broader suppression gate remains active. Never erase it.
    assert names["ORIGINAL_REPLY_AUTHENTICATION"]["decision"] in (
        "WAIT_ON_ORIGINAL_UPSTREAM_PROOF_NO_DUPLICATE_TASK",
        "ELIGIBLE_FOR_ORIGINAL_OWNER_EVIDENCE_REVIEW_ONLY",
    )
    assert names["ORIGINAL_REPLY_AUTHENTICATION"]["new_task_created"] is False
    assert names["CONTACT_AND_PROSPECT_IDENTITY"]["decision"]=="WAIT_ON_ORIGINAL_UPSTREAM_PROOF_NO_DUPLICATE_TASK"
    for gate in ("SEARCH_SOURCE_FRESHNESS","COMPETITOR_SOURCE_FRESHNESS"):
        assert names[gate]["decision"]=="EXTERNAL_OWNER_HOLD_NO_ACTION_FROM_THIS_WORKSTREAM"
    assert result["agent_tasks_created"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False
    assert result["verified_revenue_cents"] is None
    assert result["cross_cohort_join_performed"] is False


def test_signature_is_stable_across_wall_clock_changes_and_repeats():
    source=control()
    first=founder_owner_evidence_handoff(source)
    source["generated_at"]="2026-10-27T10:00:00+00:00"
    second=founder_owner_evidence_handoff(source)
    assert second["stable_handoff_signature"]==first["stable_handoff_signature"]
    assert second["original_owner_handoffs"]==first["original_owner_handoffs"]


def test_unchanged_previous_review_does_not_reissue_owner_instructions():
    original=control()
    now=datetime(2026,10,20,11,tzinfo=timezone.utc)
    prior_args=fixtures(cases=5,suppressed=2)
    prior_args.update(previous=original,now=now)
    followup=review_adaptive_commercial_intelligence(**prior_args)
    assert followup["transition"]=="UNCHANGED_COMMERCIAL_HOLD"
    packet=founder_owner_evidence_handoff(followup)
    for item in packet["original_owner_handoffs"]:
        if item["upstream_gates"]:
            assert item["decision"]=="WAIT_ON_ORIGINAL_UPSTREAM_PROOF_NO_DUPLICATE_TASK"
        elif item["gate"] in ("SEARCH_SOURCE_FRESHNESS","COMPETITOR_SOURCE_FRESHNESS"):
            assert item["decision"]=="EXTERNAL_OWNER_HOLD_NO_ACTION_FROM_THIS_WORKSTREAM"
        else:
            assert item["decision"]=="NO_NEW_EVIDENCE_NO_REPEAT_OWNER_REQUEST"
    assert packet["no_repeat_if_unchanged"] is True


@pytest.mark.parametrize("mutation",[
    lambda d: d.__setitem__("outbound_authorized",True),
    lambda d: d.__setitem__("agent_tasks_created",True),
    lambda d: d.__setitem__("decision_signature","0"*64),
    lambda d: d["active_dependency_gates"][0].__setitem__("existing_owner_lane","unapproved_agent"),
    lambda d: d["active_dependency_gates"].append(deepcopy(d["active_dependency_gates"][0])),
    lambda d: d["active_dependency_gates"][0].__setitem__(
        "original_proof_requirements_not_verified",["FAKE_PROOF"]),
])
def test_foreign_authority_forged_proof_or_owner_changes_are_rejected(mutation):
    data=control()
    mutation(data)
    with pytest.raises(ValueError):
        founder_owner_evidence_handoff(data)


def test_cli_read_only_founder_handoff_preserves_original_files(tmp_path):
    from hashlib import sha256
    root=tmp_path/"mock_original"
    root.mkdir()
    files=_test_sources(root)
    before={str(f):sha256(f.read_bytes()).hexdigest() for f in files}
    result=subprocess.run(
        [sys.executable,"-B","-m","scripts.review_commercial_adaptive_intelligence_20261020",
         "--read-only","--founder-handoff","--repo-root",str(root)],
        text=True,capture_output=True,timeout=20,
    )
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data["status"]=="ROOT_EVIDENCE_OWNER_HANDOFF_ONLY"
    assert data["site_modified"] is False
    assert data["database_writes"] is False
    assert data["agent_tasks_created"] is False
    assert {str(f):sha256(f.read_bytes()).hexdigest() for f in files}==before
    assert len(list(root.rglob("*.json")))==len(files)
