"""Release scope: original first-party source guard and review-only queue."""
import json
import shutil
from pathlib import Path
from empire_os.system_improvement_review import RESOLUTION, refresh_review_packets

BASE=Path(__file__).resolve().parents[1]
PINNED=(
    'config/harness2_evidence_guard_candidate_20261021.json',
    'config/harness2_evidence_guard_replay_receipt_20261021.json',
    'config/harness2_original_source_shadow_receipt_20261021.json',
    'empire_os/astra_harness_evidence_guard.py',
)

def prepare(root):
    for relative in PINNED:
        dest=root/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(BASE/relative,dest)
    record={
        'schema':'empire.opportunity_evidence_resolution_shadow.v1',
        'execution_authority':'none','normalized_scores_written':0,
        'factory_promotion_authorized':False,'items':[],
    }
    dest=root/RESOLUTION
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(record))
    sources={
        'runtime/conversion/latest.json':{
            'mode':'OBSERVE','execution_authority':'none',
            'counts':{'delivered_outreach_to_reply':{'entered':52,'converted':0}}},
        'runtime/buyer_acquisition/latest.json':{
            'mode':'OBSERVE','execution_authority':'none',
            'icp_priority_target_count':13,'demand_gap_count':32},
        'runtime/revenue_pulse/latest.json':{
            'mode':'OBSERVE','execution_authority':'none',
            'recognized_revenue_truth':{'recognized_revenue_cents':0}},
    }
    for relative,data in sources.items():
        dest=root/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(data))
    return root

def _harness_packets(out):
    return [item for item in out['packets']
            if item['type']=='ASTRA_HARNESS2_SKILL_REVIEW']

def test_bounded_existing_review_refresh_is_idempotent_and_never_dispatches(tmp_path):
    root=prepare(tmp_path)
    first=refresh_review_packets(root)
    second=refresh_review_packets(root)
    assert len(_harness_packets(first))==len(_harness_packets(second))==1
    assert first['task_count']==second['task_count']==1
    assert second['new_or_changed_review_packets']==0
    assert not (root/'runtime/departments/work/ready').exists()
    assert second['department_work_queue_mutated'] is False
    item=_harness_packets(first)[0]
    stored=json.loads((root/item['path']).read_text())
    assert stored['auto_dispatch_eligible'] is False
    assert stored['approved_for_implementation'] is False
    assert stored['allow_payment'] is False
    assert stored['allow_outbound'] is False
    assert stored['allow_db_migration'] is False

def test_missing_original_revenue_source_stops_queue_promotion(tmp_path):
    root=prepare(tmp_path)
    (root/'runtime/revenue_pulse/latest.json').unlink()
    out=refresh_review_packets(root)
    assert len(_harness_packets(out))==0

def test_tampered_replay_stops_queue_promotion(tmp_path):
    root=prepare(tmp_path)
    receipt=root/'config/harness2_evidence_guard_replay_receipt_20261021.json'
    data=json.loads(receipt.read_text())
    data['measured']['guarded_passed']=99
    receipt.write_text(json.dumps(data))
    out=refresh_review_packets(root)
    assert len(_harness_packets(out))==0

def test_invalid_conversion_stage_stops_queue_promotion(tmp_path):
    root=prepare(tmp_path)
    evidence=root/'runtime/conversion/latest.json'
    data=json.loads(evidence.read_text())
    data['counts']['delivered_outreach_to_reply']['converted']=53
    evidence.write_text(json.dumps(data))
    out=refresh_review_packets(root)
    assert len(_harness_packets(out))==0
