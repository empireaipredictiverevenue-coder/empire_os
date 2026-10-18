"""Real-status receipt classification cannot become customer financial proof."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,pytest

from empire_os.enterprise_finance_evidence_readiness import (
    SOURCE_DEFINITIONS,review_finance_source_readiness,
)
from scripts.review_enterprise_finance_evidence_readonly import main as cli

NOW=datetime(2026,10,18,14,7,tzinfo=timezone.utc)


def _snapshots():
    return {
        "revenue_pulse":{
            "schema_version":"empire.revenue-pulse.v3",
            "mode":"OBSERVE","execution_authority":"none",
            "generated_at":NOW.isoformat(),
            "snapshot_source":"canonical_empiredb_postgres",
            "execution_allowed":False,"payment_mutation":False,
            "accounting_mutation":False,
            "recognized_revenue_truth":{
                "recognized_revenue_cents":0,
                "forecast_included_in_truth":False,
            },
            "current_window":{
                "hours":24,
                "recognized_revenue_cents":0,
                "verified_payments":0,"fulfilments":0,
            },
        },
        "economic_memory":{
            "schema_version":"empire.economic_memory.v1",
            "mode":"OBSERVE","execution_authority":"none",
            "generated_at":NOW.isoformat(),
            "accounting_authority":"none","commercial_authority":"none",
            "promoted_learning":False,"calibration_evidence_count":0,
        },
        "buyer_capacity":{
            "schema_version":"empire.buyer_capacity_readiness.v1",
            "mode":"OBSERVE","execution_authority":"none",
            "observed_at":NOW.isoformat(),
            "capacity_verified":0,"terms_verified":0,
            "delivery_verified":0,"revenue_recognition":False,
        },
    }


def _write(root,source,packet):
    rel=next(row[1] for row in SOURCE_DEFINITIONS if row[0]==source)
    p=Path(root)/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(packet))
    return p


@pytest.fixture
def sample(tmp_path):
    values=_snapshots()
    for source,packet in values.items():
        _write(tmp_path,source,packet)
    return tmp_path


def test_valid_internal_observations_never_promote_zero_to_audited_revenue(sample):
    report=review_finance_source_readiness(sample,as_of=NOW)
    assert report["status"]=="SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED"
    assert report["current_internal_source_snapshot_count"]==3
    assert report["revenue_pulse_observation"]["reported_24h_recognized_cents"]==0
    assert report["revenue_pulse_observation"]["reported_24h_verified_payment_count"]==0
    assert report["economic_memory_observation"]["reported_calibration_evidence_count"]==0
    assert report["buyer_capacity_observation"]["reported_verified_capacity_count"]==0
    assert report["required_proofs_not_admitted_count"]==7
    assert not report["actual_recognised_revenue_independently_verified"]
    assert not report["customer_invoice_or_statement_approved"]
    assert not report["report_distribution_authorized"]
    assert not report["empiredb_reads_performed"]
    assert not report["canonical_single_event_reader_role_provisioning_independently_checked"]
    assert not report["source_file_hash_is_external_signature"]
    for record in report["source_receipts"].values():
        assert record["status"]=="INTERNAL_SNAPSHOT_ONLY"
        assert len(record["local_file_sha256"])==64
        assert record["original_financial_rows_independently_verified"] is False


def test_file_missing_invalid_schema_or_mutated_authority_all_hold(sample):
    for source,field,value in (
        ("revenue_pulse","schema_version","made.up.v9"),
        ("economic_memory","execution_authority","write"),
        ("buyer_capacity","mode","LIVE"),
    ):
        src=_snapshots()
        src[source][field]=value
        _write(sample,source,src[source])
        result=review_finance_source_readiness(sample,as_of=NOW)
        assert result["status"]=="HOLD_MISSING_STALE_OR_INCONSISTENT_SOURCE_OBSERVATIONS"
        assert result["source_receipts"][source]["status"]=="SOURCE_UNAVAILABLE_OR_INVALID"
        assert not result["report_distribution_authorized"]
        _write(sample,source,_snapshots()[source])
    path=sample/SOURCE_DEFINITIONS[0][1]
    path.unlink()
    denied=review_finance_source_readiness(sample,as_of=NOW)
    assert denied["status"].startswith("HOLD_")
    assert denied["current_internal_source_snapshot_count"]==2


def test_stale_future_or_symlinked_source_holds(sample,tmp_path):
    original=_snapshots()
    original["revenue_pulse"]["generated_at"]=(NOW-timedelta(days=3)).isoformat()
    _write(sample,"revenue_pulse",original["revenue_pulse"])
    result=review_finance_source_readiness(sample,as_of=NOW)
    assert result["source_receipts"]["revenue_pulse"]["status"]=="STALE_OR_FUTURE_INTERNAL_SNAPSHOT"
    assert result["status"].startswith("HOLD_")
    original=_snapshots()
    original["revenue_pulse"]["generated_at"]=(NOW+timedelta(hours=2)).isoformat()
    _write(sample,"revenue_pulse",original["revenue_pulse"])
    assert review_finance_source_readiness(sample,as_of=NOW)["status"].startswith("HOLD_")
    p=sample/SOURCE_DEFINITIONS[0][1]
    p.unlink()
    protected=tmp_path/"other_file.json"
    protected.write_text(json.dumps(_snapshots()["revenue_pulse"]))
    p.symlink_to(protected)
    bad=review_finance_source_readiness(sample,as_of=NOW)
    assert bad["source_receipts"]["revenue_pulse"]["status"]=="SOURCE_UNAVAILABLE_OR_INVALID"


def test_false_revenue_source_relabel_or_unbalanced_windows_are_not_trusted(sample):
    raw=_snapshots()["revenue_pulse"]
    for k,v in (
        ("snapshot_source","unsourced_api"),
        ("payment_mutation",True),
        ("execution_allowed",True),
    ):
        original=deepcopy(raw)
        original[k]=v
        _write(sample,"revenue_pulse",original)
        state=review_finance_source_readiness(sample,as_of=NOW)
        assert state["revenue_pulse_observation"]["status"]=="UNKNOWN_NOT_PROVEN"
        assert state["revenue_pulse_observation"]["reported_24h_recognized_cents"] is None
        assert state["status"].startswith("HOLD_")
    wrong=deepcopy(raw)
    wrong["recognized_revenue_truth"]["recognized_revenue_cents"]=100
    _write(sample,"revenue_pulse",wrong)
    state=review_finance_source_readiness(sample,as_of=NOW)
    assert state["status"].startswith("HOLD_")
    assert state["revenue_pulse_observation"]["reported_24h_recognized_cents"] is None


def test_positive_snapshots_remain_observations_not_verified_finance(sample):
    updated=_snapshots()
    updated["revenue_pulse"]["recognized_revenue_truth"]["recognized_revenue_cents"]=12500
    updated["revenue_pulse"]["current_window"]["recognized_revenue_cents"]=12500
    updated["revenue_pulse"]["current_window"]["verified_payments"]=1
    updated["buyer_capacity"]["capacity_verified"]=3
    updated["buyer_capacity"]["terms_verified"]=1
    for source,packet in updated.items():
        _write(sample,source,packet)
    state=review_finance_source_readiness(sample,as_of=NOW)
    assert state["status"]=="SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED"
    assert state["revenue_pulse_observation"]["reported_24h_recognized_cents"]==12500
    assert state["buyer_capacity_observation"]["reported_verified_capacity_count"]==3
    assert state["actual_recognised_revenue_independently_verified"] is False
    assert state["independent_money_movement_proof_obtained"] is False


def test_no_arg_cli_blocks_and_explicit_read_only_does_not_write(tmp_path,capsys):
    assert cli([],repo_root=tmp_path)==2
    status=json.loads(capsys.readouterr().out)
    assert status["status"]=="HOLD_EXPLICIT_READ_ONLY_REQUIRED"
    assert cli(["--read-only"],repo_root=tmp_path)==2
    status=json.loads(capsys.readouterr().out)
    assert status["status"].startswith("HOLD_")
    assert list(tmp_path.iterdir())==[]


def test_external_customer_finance_never_claimed_without_original_rows(sample):
    report=review_finance_source_readiness(sample,as_of=NOW)
    assert report["canonical_database"]=="EmpireDB"
    assert report["required_proofs_not_admitted_count"]==len(
        report["independent_finance_evidence_requirements"])
    for gap in report["independent_finance_evidence_requirements"]:
        assert gap["status"]=="NO_INDEPENDENT_PROOF_ADMITTED"
        assert isinstance(gap["required_to_close"],str) and gap["required_to_close"]
    assert not report["customer_record_completeness_verified"]
    assert not report["commercial_automation_authorized"]



def test_existing_enterprise_draft_verifier_opt_in_finance_readiness(
    monkeypatch,sample,capsys,
):
    """No route or existing report payload change; bounded opt-in only."""
    from scripts import preview_enterprise_report_evidence_readonly as combined
    import empire_os.predictive_revenue_enterprise_report as report
    monkeypatch.setattr(report,"build_enterprise_diagnostic_report",
                        lambda root:{"internal_test_report":True})
    monkeypatch.setattr(combined,"validate_enterprise_report_before_render",
                        lambda packet:{
                            "status":"INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED",
                            "verified_finding_count":0,
                            "customer_delivery_authorized":False,
                        })
    import empire_os.enterprise_finance_evidence_readiness as runtime
    original=runtime.review_finance_source_readiness
    monkeypatch.setattr(runtime,"review_finance_source_readiness",
                        lambda root:original(root,as_of=NOW))
    status=combined.main(["--read-only","--format","verify",
                          "--finance-readiness"],repo_root=sample)
    assert status==0
    response=json.loads(capsys.readouterr().out)
    assert response["report_guard"]["verified_finding_count"]==0
    assert response["finance_source_readiness"]["required_proofs_not_admitted_count"]==7
    assert response["finance_source_readiness"]["source_file_hash_is_external_signature"] is False
    assert response["customer_delivery_authorized"] is False
    assert status==0
    status=combined.main(["--read-only","--format","markdown",
                          "--finance-readiness"],repo_root=sample)
    assert status==2
    error=json.loads(capsys.readouterr().out)
    assert error["status"]=="HOLD_FINANCE_READINESS_REQUIRES_VERIFY_FORMAT"
    # A missing status file cannot be interpreted as a successful review.
    (sample/SOURCE_DEFINITIONS[0][1]).unlink()
    status=combined.main(["--read-only","--format","verify",
                          "--finance-readiness"],repo_root=sample)
    assert status==2
    hold=json.loads(capsys.readouterr().out)
    assert hold["finance_source_readiness"]["status"].startswith("HOLD_")
