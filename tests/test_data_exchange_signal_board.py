"""Construction buyer signal board: strict source truth, synthetic fixtures only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.data_exchange_signal_board import build_signal_board
from empire_os.data_exchange_construction import build_construction_preview
from test_data_exchange_agi_bridge import NOW, source, procurement, row

def board(snapshots=None, *, proc=None, limit=24, at=NOW):
    return build_signal_board(
        source_snapshots=source() if snapshots is None else snapshots,
        procurement=proc, assessed_at=at, limit=limit,
    )

def sequence(statuses=("non-permissioned","permissioned","permissioned"),
             *, shared=True):
    obs=[NOW-timedelta(days=3-i) for i in range(len(statuses))]
    return [build_construction_preview(
        [row(t, state if shared or i==0 else state) for state in [statuses[i]]],
        observed_at=t,
    ) for i,t in enumerate(obs)]

def test_zero_change_is_not_a_fake_lead():
    result=board()
    assert result["feed_status"]=="NO_OBSERVED_FIELD_CHANGES"
    assert result["total_validated_changes"]==0
    assert result["review_queue"]==[]
    assert result["latest_reflected_in_queue"]==0
    assert result["field_lineage_review_required"] is True
    assert result["customer_delivery_enabled"] is False
    assert result["data_resale_authorized"] is False
    assert result["execution_authority"]=="NONE"

def test_one_observed_source_status_transition_is_not_buyer_intent():
    result=board(source(changed=True))
    assert result["feed_status"]=="OBSERVED_CHANGES_REVIEW_ONLY"
    assert result["total_validated_changes"]==1
    assert result["queue_count"]==1
    event=result["review_queue"][0]
    assert event["review_priority"]=="REVIEW"
    assert event["source_record_id"]=="1739547"
    assert event["source_url"]=="https://www.planning.data.gov.uk/entity/1739547"
    assert event["latest_snapshot_status"]=="STILL_REFLECTED_IN_LATEST_SAMPLE"
    assert event["review_action"]=="VERIFY_OFFICIAL_SOURCE_REVISION_AND_FIELD_RIGHTS"
    assert event["observed_field_changes"]["planning_permission_status"]=={
        "previous":"non-permissioned","current":"permissioned",
    }
    assert event["prediction_available"] is False
    assert event["commercial_signal"] is False
    assert event["source_change_not_publication_time"] is True
    assert "not-applicable" not in str(result)

def test_independent_procurement_never_implies_project_link():
    result=board(source(changed=True),proc=procurement())
    assert result["procurement_notices_in_sample"]==1
    assert len(result["required_source_attributions"])==2
    assert result["cross_source_project_join_verified"] is False
    assert "PRIVATE-TENDER-DESCRIPTION" not in str(result)
    assert "private@example.org" not in str(result)
    assert result["rights_clearance"]=="PENDING_INDEPENDENT_FIELD_REVIEW"
    assert result["pending_field_review_count"]>0

def test_event_superseded_by_later_valid_observation():
    source_history=sequence(("non-permissioned","permissioned","non-permissioned"))
    result=board(source_history)
    assert result["total_validated_changes"]==2
    assert {e["latest_snapshot_status"] for e in result["review_queue"]}=={
        "STILL_REFLECTED_IN_LATEST_SAMPLE",
        "SUPERSEDED_BY_LATER_OBSERVATION",
    }
    assert result["review_queue"][0]["observed_field_changes"]["planning_permission_status"]["current"]=="non-permissioned"
    assert result["review_queue"][1]["review_action"]=="RECONCILE_SOURCE_OBSERVATION_HISTORY"

def test_event_previous_changes_remain_reflected_if_unreverted():
    source_history=sequence(("non-permissioned","permissioned","permissioned"))
    result=board(source_history)
    assert result["total_validated_changes"]==1
    assert result["review_queue"][0]["latest_snapshot_status"]=="STILL_REFLECTED_IN_LATEST_SAMPLE"

def test_coverage_absence_does_not_mean_new_or_deleted_projects():
    obs=[NOW-timedelta(days=i) for i in [2,1]]
    first=build_construction_preview([row(obs[0])], observed_at=obs[0])
    later=build_construction_preview(
        [row(obs[1]), {**row(obs[1]), "record_id":"1722645",
          "source_url":"https://www.planning.data.gov.uk/entity/1722645"}],
        observed_at=obs[1],
    )
    result=board([first,later])
    assert result["total_validated_changes"]==0
    assert result["coverage_gap_count"]==1
    assert result["sample_coverage_changes"][0]["newly_sampled_ids"]==["1722645"]
    assert result["sample_coverage_changes"][0]["new_project_claim"] is False
    assert result["sample_coverage_changes"][0]["removed_project_claim"] is False

def test_unmatched_window_is_held_not_accepted_as_event():
    times=[NOW-timedelta(days=2),NOW-timedelta(days=1)]
    a=build_construction_preview([row(times[0])], observed_at=times[0])
    b=build_construction_preview([{**row(times[1]),"record_id":"1722645",
       "source_url":"https://www.planning.data.gov.uk/entity/1722645"}],
       observed_at=times[1])
    result=board([a,b])
    assert result["feed_status"]=="HOLD_HISTORY_GAPS"
    assert result["held_comparison_count"]==1
    assert result["review_queue"]==[]
    assert "NO_SHARED_OBSERVED_ENTITIES" in result["held_comparisons"][0]["holds"]

def test_feed_is_deterministic_and_carries_existing_source_hash():
    result=board(source(changed=True))
    assert result==board(source(changed=True))
    assert len(result["source_history_sha256"])==64
    assert len(result["source_evidence_sha256"])==64

@pytest.mark.parametrize("field,value",[
    ("customer_delivery_enabled",True),
    ("data_resale_authorized",True),
    ("execution_authority","EXECUTE"),
])
def test_source_snapshots_cannot_grant_authority(field,value):
    data=source(changed=True)
    data[-1][field]=value
    with pytest.raises(ValueError):
        board(data)

def test_personal_data_field_rejected():
    data=source(changed=True)
    data[-1]["records"][0]["contact_email"]="someone@example.org"
    with pytest.raises(ValueError):
        board(data)

def test_source_url_mismatch_rejected():
    data=source(changed=True)
    data[-1]["records"][0]["source_url"]="https://example.org/entity/1739547"
    with pytest.raises(ValueError):
        board(data)

def test_no_forged_licensing_or_procurement():
    data=procurement()
    data["data_resale_authorized"]=True
    with pytest.raises(ValueError):
        board(source(changed=True),proc=data)

@pytest.mark.parametrize("bad",[0,True,-1,65,1.1,"5"])
def test_strict_display_bound(bad):
    with pytest.raises(ValueError):
        board(limit=bad)

def test_naive_time_and_stale_source_rejected():
    with pytest.raises(ValueError):
        board(at=datetime(2026,10,14))
    with pytest.raises(ValueError):
        board(at=NOW+timedelta(days=120))

def test_no_new_agent_db_transport_or_customer_claims():
    result=board(source(changed=True))
    assert result["production_writes"] is False
    assert result["outbound_enabled"] is False
    assert result["payment_execution"] is False
    assert result["actual_revenue"] is False
    assert result["forecast_accuracy_verified"] is False
    assert result["buyer_interest_verified"] is False
    assert result["source_authenticity"]=="NOT_INDEPENDENTLY_VERIFIED"
    assert result["history_integrity"]=="LOCAL_HASH_CHAIN_UNANCHORED"


def test_truncation_keeps_total_count_not_misleading_completeness():
    hist=sequence(("non-permissioned","permissioned","non-permissioned"))
    result=board(hist,limit=1)
    assert result["total_validated_changes"]==2
    assert result["queue_count"]==1
    assert result["queue_truncated"] is True
    assert result["latest_reflected_in_queue"]==1


def test_agi_receives_bounded_observed_change_review_not_commercial_signal():
    from empire_os.data_exchange_agi_bridge import review_data_exchange_agi
    packet=review_data_exchange_agi(
        source_snapshots=source(changed=True),tenant_id="internal",
        assessed_at=NOW,
    )
    assert packet["signal_board_status"]=="OBSERVED_CHANGES_REVIEW_ONLY"
    assert packet["signal_board_rights_status"]=="PENDING_INDEPENDENT_FIELD_REVIEW"
    assert len(packet["signal_review_queue"])==1
    assert packet["signal_review_queue"][0]["execution_ready"] is False
    assert packet["customer_delivery_enabled"] is False
    assert packet["human_level_agi_claimed"] is False
    assert packet["recommended_workstream"]=="review_dataset_rights"


def test_one_shot_cli_presents_bounded_internal_signal_board(tmp_path,capsys):
    import json
    from scripts.preview_data_exchange_signal_board import main
    older,later=source(changed=True)
    files=[tmp_path/"older.json",tmp_path/"later.json"]
    files[0].write_text(json.dumps(older),encoding="utf-8")
    files[1].write_text(json.dumps(later),encoding="utf-8")
    before=sorted(f.name for f in tmp_path.iterdir())
    assert main(["--snapshots",str(files[0]),str(files[1])])==0
    report=json.loads(capsys.readouterr().out)
    assert report["total_validated_changes"]==1
    assert report["customer_delivery_enabled"] is False
    assert report["source_history_sha256"]
    assert report["production_writes"] is False
    assert sorted(f.name for f in tmp_path.iterdir())==before


def test_cli_rejects_symlink_and_never_prints_private_source(tmp_path,capsys):
    import json
    from scripts.preview_data_exchange_signal_board import main
    secret=tmp_path/"secret.json"
    secret.write_text('{"email":"PRIVATE_SOURCE@example.org"}')
    link=tmp_path/"link.json"
    link.symlink_to(secret)
    assert main(["--snapshots",str(link),str(link)])==2
    report=json.loads(capsys.readouterr().out)
    assert report["feed_status"]=="HOLD_INVALID_OR_UNVERIFIED_SOURCE"
    assert "PRIVATE_SOURCE" not in str(report)
    assert report["execution_authority"]=="NONE"


def test_cli_rejects_unapproved_forged_rights_claim(tmp_path,capsys):
    import json
    from scripts.preview_data_exchange_signal_board import main
    before,after=source(changed=True)
    after["rights_review_eligible"]=True
    a,b=tmp_path/"a.json",tmp_path/"b.json"
    a.write_text(json.dumps(before),encoding="utf-8")
    b.write_text(json.dumps(after),encoding="utf-8")
    assert main(["--snapshots",str(a),str(b)])==2
    report=json.loads(capsys.readouterr().out)
    assert report["customer_delivery_enabled"] is False
