"""Research cohort freeze guards and deterministic prospective ranking tests."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import json
import os

import pytest
from empire_os import predictive_cloud_prospective_freeze as freeze


def training_rows():
    editions=(("2026-02-09","2026-05-06",13982),
              ("2026-05-06","2026-08-03",14310),
              ("2026-08-03","2026-11-13",14648))
    out=[]
    for a,b,n in editions:
        for idx in range(n):
            changed=idx%34==0
            out.append({
                "features_available_after_publisher_edition":a,
                "label_available_after_publisher_edition":b,
                "development_stage_at_asof":"Planning Application Submitted" if idx%2 else "Operational",
                "technology_at_asof":"Solar Photovoltaics" if idx%3 else "Wind Onshore",
                "published_stage_changed":changed,
                "label_is_publisher_change_not_business_outcome":True,
                "training_admission_allowed":False,
            })
    return out


def states(n=14967):
    return {
        str(i+1):{
            "status":"Planning Application Submitted" if i%2 else "Operational",
            "technology":"Solar Photovoltaics" if i%3 else "Wind Onshore",
        }
        for i in range(n)
    }


def test_frozen_scores_deterministic_and_only_asof_research():
    train=training_rows()
    first,metadata=freeze._build_scores(states(),train,freeze.CUTOFF)
    second,repeat=freeze._build_scores(states(),train,freeze.CUTOFF)
    assert first==second and metadata==repeat
    rows=[json.loads(row) for row in first.splitlines()]
    assert len(rows)==14967
    assert metadata["score_rows"]==14967
    assert metadata["scored_top_n_predeclared"]==500
    assert len({x["public_project_key_sha256"] for x in rows})==14967
    assert metadata["model_research_parameters"]["training_rows"]==42940
    assert metadata["model_research_parameters"]["no_future_outcome_data"]
    assert all(x["next_official_publisher_outcome_unobserved"] is True
               and x["production_model_training_authorized"] is False
               and x["score_is_calibrated_forecast"] is False
               and x["score_is_customer_purchase_probability"] is False
               and x["customer_revenue_predicted"] is False
               for x in rows)
    assert all(x["asof_publisher_date"]=="2026-11-13" for x in rows)
    assert all(not set(x).intersection({
        "published_stage_changed","customer_id","contact","project_ref",
        "email","operator","future_stage"}) for x in rows)
    assert rows==sorted(rows,key=lambda r:(-r["stage_change_research_score"],
                                           r["public_project_key_sha256"]))


def test_future_training_rows_rejected_before_freeze():
    train=training_rows()
    train[-1]["label_available_after_publisher_edition"]="2027-02-01"
    with pytest.raises(ValueError,match="TRAINING_ASOF"):
        freeze._build_scores(states(),train,freeze.CUTOFF)


def test_asof_cohort_count_and_date_pinned():
    train=training_rows()
    with pytest.raises(ValueError,match="ASOF_OR_COHORT"):
        freeze._build_scores(states(17),train,freeze.CUTOFF)
    with pytest.raises(ValueError,match="ASOF_OR_COHORT"):
        freeze._build_scores(states(),train,"2027-02-01")


def test_training_edition_inventory_must_be_exact():
    train=training_rows()
    train[0]["label_available_after_publisher_edition"]="2026-07-01"
    with pytest.raises(ValueError,match="TRAINING_EDITION_INVENTORY"):
        freeze._build_scores(states(),train,freeze.CUTOFF)


def test_content_addressed_write_create_once_and_detect_tamper(tmp_path):
    p=tmp_path/"freeze"/"data.jsonl"
    assert freeze._immutable_create(p,b'{"a":1}\n') is True
    assert p.parent.stat().st_mode&0o777==0o700
    assert p.stat().st_mode&0o777==0o600
    assert freeze._immutable_create(p,b'{"b":2}\n') is False
    assert p.read_bytes()==b'{"a":1}\n'
    good=sha256(p.read_bytes()).hexdigest()
    assert freeze._verified_private_file(p,good,100)==p.read_bytes()
    p.write_bytes(b'{"b":2}\n')
    with pytest.raises(ValueError,match="SHA_MISMATCH"):
        freeze._verified_private_file(p,good,100)


def test_private_destination_permission_and_symlink_held(tmp_path):
    p=tmp_path/"untrusted"
    p.mkdir(mode=0o755)
    with pytest.raises(ValueError,match="DIRECTORY_PERMISSIONS"):
        freeze._immutable_create(p/"freeze",b"x")
    target=tmp_path/"target"
    target.write_text("do not touch")
    symlink=tmp_path/"link"
    symlink.symlink_to(target)
    with pytest.raises(ValueError,match="EXISTING_OBJECT_UNTRUSTED"):
        freeze._immutable_create(symlink,b"bad")
    assert target.read_text()=="do not touch"


def test_no_noncanonical_freeze_and_no_missing_commit(tmp_path):
    status=freeze.freeze_once(tmp_path)
    assert status["status"]=="NONCANONICAL_PROSPECTIVE_FREEZE_HELD"
    assert not (tmp_path/freeze.RECEIPT).exists()
    with pytest.raises(ValueError,match="NO_COMMITTED_PROSPECTIVE_RESEARCH_FREEZE"):
        freeze.verify_frozen_cohort(tmp_path)


def test_original_systemd_owner_attests_only_research_freeze():
    from datetime import datetime, timezone
    from unittest.mock import patch
    from empire_os import data_brokerage_enterprise_feed as feed
    writes=[]
    fake_freeze={
        "status":"VERIFIED_IMMUTABLE_PROSPECTIVE_RESEARCH_FREEZE",
        "frozen_at":"2026-11-18T18:59:43+00:00",
        "publisher_asof_date":"2026-11-13",
        "research_scored_projects":14967,
        "score_object_sha256":"a"*64,
        "model_training_authorized":False,
    }
    with patch.dict(os.environ,{"INVOCATION_ID":"b"*32}), patch.object(
            feed,"_atomic",side_effect=lambda p,raw:writes.append(json.loads(raw))):
        actual=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},
            now=datetime(2026,11,18,19,0,tzinfo=timezone.utc),
            frozen_research=fake_freeze)
    assert actual["timer_receipt_written"] is True and len(writes)==1
    assert writes[0]["prospective_research_cohort_rows"]==14967
    assert writes[0]["prospective_research_asof"]=="2026-11-13"
    assert writes[0]["prospective_research_frozen_at"]==fake_freeze["frozen_at"]
    assert writes[0]["prospective_production_predictions_produced"]==0
    assert writes[0]["prospective_model_training_authorized"] is False
    with patch.dict(os.environ,{"INVOCATION_ID":"MANUAL"}), patch.object(
            feed,"_atomic",side_effect=AssertionError("NO_FALSE_SCHEDULED_RECEIPT")):
        denied=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},frozen_research=fake_freeze)
    assert denied["timer_receipt_written"] is False


def test_scoring_calibration_does_not_promote_production_prediction():
    train=training_rows()
    _,details=freeze._build_scores(states(),train,freeze.CUTOFF)
    model=details["model_research_parameters"]
    assert model["model_authority"]=="RESEARCH_OBSERVE_ONLY"
    assert model["no_customer_prediction_model"] is True
    assert len(model["stage_smoothed_rates"])>=1
    assert len(model["stage_and_technology_smoothed_rates"])>=1
    assert all(0<row["rate"]<1 for row in model["stage_smoothed_rates"])
