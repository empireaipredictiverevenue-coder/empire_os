"""Untrusted report object cannot fabricate verified findings or client money."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
import json
import sys
import types

import pytest

from empire_os.enterprise_report_claim_guard import (
    validate_enterprise_report_before_render,guarded_enterprise_report_render,
)

NOW=datetime(2026,10,18,12,40,tzinfo=timezone.utc)


def make_report(*,with_finding=False):
    keys=[f"chapter_{i:02d}" for i in range(12)]
    finding=None
    if with_finding:
        finding={
            "finding_id":"pilot_001","chapter_key":keys[0],
            "headline":"Candidate stage latency",
            "evidence_status":"SOURCE_CUSTODY_AND_COHORT_NOT_INDEPENDENTLY_VERIFIED",
            "automated_client_claim_allowed":False,
            "causal_conclusion_confirmed":False,
            "recovered_revenue_cents":None,
            "investment_return_confirmed":False,
            "eligible_population":20,"affected_population":5,
            "affected_rate_percent":25.0,
            "source_references_caller_supplied":["source:case_pilot_001"],
            "illustrative_contribution_scenario":None,
        }
    findings=[finding] if finding else []
    chapters=[
        {
            "chapter_key":key,"title":f"Chapter {i+1}",
            "finding_count":1 if i==0 and finding else 0,
            "specific_claims_submitted_for_review":[deepcopy(finding)]
                if i==0 and finding else [],
            "decision_quality":"INVESTIGATION_REQUIRED",
            "existing_source_snapshots_present_not_verified":{"revenue_pulse":False},
            "source_evidence_complete":False,
            "client_claim_approved":False,
        }
        for i,key in enumerate(keys)
    ]
    appendix=[{
        "source_ref":"source:case_pilot_001",
        "used_by_findings":["pilot_001"],
        "original_record_read_by_this_report":False,
        "tenant_scope_confirmed":False,
        "source_integrity_verified":False,
        "verification_state":"SOURCE_REFERENCE_CLAIM_ONLY",
    }] if finding else []
    decisions=[{
        "finding_id":"pilot_001",
        "decision_status":"PENDING_SOURCE_REVIEW_AND_OWNER_APPROVAL",
        "spend_authorized":False,
    }] if finding else []
    return {
        "schema_version":"empire.predictive_revenue.enterprise_diagnostic_report.v1",
        "report_disposition":"INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE",
        "report_type":"DETAILED_INTERNAL_EVIDENCE_REVIEW",
        "product_code":"predictive_revenue_diagnostic",
        "mode":"OBSERVE","execution_authority":"none",
        "case_ref":"PILOT_INTERNAL_01",
        "as_of_utc":NOW.isoformat(),
        "catalog_changed":False,"new_os_or_database_created":False,
        "production_activated":False,"financial_write":False,
        "model_learning_promoted":False,"outbound_enabled":False,
        "executive_summary":{
            "decision":"HOLD_CUSTOMER_DIAGNOSTIC_CLAIMS",
            "observed_client_revenue_cents":None,
            "verified_customer_opportunity_value_cents":None,
            "forecast_improvement_claim":None,
            "recommended_approved_spend_cents":None,
        },
        "source_traceability":{
            "source_type":"EXISTING_EMPIREOS_PRODUCT_WORKBENCH",
            "workbench_schema":"empire.predictive_revenue.product_workbench.v1",
            "original_customer_source_verified":False,
            "independent_financial_reconciliation_verified":False,
            "time_ordered_forecast_holdout_verified":False,
            "tenant_access_authorized_for_customer":False,
        },
        "source_extract_reconciliation":{
            "recognized_revenue_daily_total_verified":False,
            "tenant_access_verified":False,
            "usable_in_customer_report_as_verified_actual":False,
        },
        "release_gate":{
            "original_client_records_verified":False,
            "tenant_permissions_verified":False,
            "finance_reconciliation_signed":False,
            "findings_source_audited":False,
            "human_report_reviewed":False,
            "client_release_approved":False,
            "customer_delivery_enabled":False,
        },
        "required_reviewer_signoffs":[
            {
                "reviewer_role":r,
                "decision":"PENDING_FOUNDER_RELEASE" if i==3
                            else "PENDING_INDEPENDENT_REVIEW",
                "verified_signature_ref":None,
            }
            for i,r in enumerate((
                "Client-authorised data custodian","Finance reconciliation owner",
                "Commercial operations owner","Empire AI founder release gate"))
        ],
        "no_ai_slop_contract":{k:True for k in (
            "no_generic_growth_claims","no_unsupported_money_values",
            "no_fabricated_customers_or_outcomes",
            "each_finding_requires_cohort_denominator",
            "each_finding_requires_source_refs",
            "each_finding_requires_testable_alternative",
            "review_before_client_delivery",
        )},
        "chapter_count":12,
        "chapters":chapters,
        "finding_register":findings,
        "evidence_appendix":appendix,
        "decision_register":decisions,
        "completeness":{
            "chapters":12,
            "chapters_with_submitted_findings":1 if finding else 0,
            "chapters_without_submitted_findings":keys[1:] if finding else keys,
            "findings_unverified":len(findings),
            "findings_verified":0,
            "claims_approved_for_customer_report":0,
        },
    }


def test_empty_and_nonempty_internal_drafts_validate_only_as_unverified():
    for report in (make_report(),make_report(with_finding=True)):
        result=validate_enterprise_report_before_render(report)
        assert result["status"]=="INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED"
        assert result["unverified_finding_count"]==len(report["finding_register"])
        assert result["verified_finding_count"]==0
        assert result["customer_delivery_authorized"] is False
        assert result["underlying_finance_audited"] is False
        assert len(result["local_report_sha256"])==64
        assert result["digest_is_publisher_signature"] is False


@pytest.mark.parametrize("path,value",[
    (("completeness","findings_verified"),42),
    (("completeness","claims_approved_for_customer_report"),1),
    (("completeness","findings_unverified"),1),
    (("release_gate","client_release_approved"),True),
    (("release_gate","customer_delivery_enabled"),True),
    (("source_traceability","original_customer_source_verified"),True),
    (("source_extract_reconciliation","recognized_revenue_daily_total_verified"),True),
    (("executive_summary","observed_client_revenue_cents"),250000000),
    (("no_ai_slop_contract","no_unsupported_money_values"),False),
    (("chapters",0,"source_evidence_complete"),True),
    (("chapters",0,"client_claim_approved"),True),
    (("required_reviewer_signoffs",0,"verified_signature_ref"),"fake-signature"),
])
def test_unverified_escalation_or_count_forgery_is_rejected(path,value):
    draft=make_report()
    ref=draft
    for part in path[:-1]: ref=ref[part]
    ref[path[-1]]=value
    with pytest.raises(ValueError,match="ENTERPRISE_REPORT_EVIDENCE_HOLD"):
        validate_enterprise_report_before_render(draft)


@pytest.mark.parametrize("path,value",[
    (("finding_register",0,"evidence_status"),"VERIFIED"),
    (("finding_register",0,"recovered_revenue_cents"),92000000),
    (("finding_register",0,"investment_return_confirmed"),True),
    (("finding_register",0,"affected_population"),99),
    (("finding_register",0,"affected_rate_percent"),99),
    (("finding_register",0,"source_references_caller_supplied"),["owner@example.com"]),
    (("chapters",0,"finding_count"),2),
    (("evidence_appendix",0,"source_integrity_verified"),True),
    (("evidence_appendix",0,"original_record_read_by_this_report"),True),
    (("decision_register",0,"spend_authorized"),True),
])
def test_findings_appendix_and_decisions_all_cross_checked(path,value):
    draft=make_report(with_finding=True)
    current=draft
    for part in path[:-1]: current=current[part]
    current[path[-1]]=value
    with pytest.raises(ValueError,match="ENTERPRISE_REPORT_EVIDENCE_HOLD"):
        validate_enterprise_report_before_render(draft)


def test_full_report_ref_integrity_including_appendix_and_chapter_copy():
    report=make_report(with_finding=True)
    report["evidence_appendix"][0]["used_by_findings"]=[]
    with pytest.raises(ValueError,match="SOURCE"):
        validate_enterprise_report_before_render(report)
    report=make_report(with_finding=True)
    report["chapters"][0]["specific_claims_submitted_for_review"][0]["headline"]="overstated"
    with pytest.raises(ValueError,match="CHAPTER_FINDING_LIST"):
        validate_enterprise_report_before_render(report)


def test_render_adapters_validate_before_calling_existing_html_or_markdown(
    monkeypatch
):
    html=types.ModuleType("empire_os.predictive_revenue_report_presentation")
    md=types.ModuleType("empire_os.predictive_revenue_enterprise_report")
    calls=[]
    html.render_enterprise_report_html=lambda report:(calls.append("html") or "<p>INTERNAL</p>")
    md.render_enterprise_report_markdown=lambda report:(calls.append("markdown") or "INTERNAL")
    monkeypatch.setitem(sys.modules,html.__name__,html)
    monkeypatch.setitem(sys.modules,md.__name__,md)
    assert guarded_enterprise_report_render(make_report(),format="html")=="<p>INTERNAL</p>"
    assert guarded_enterprise_report_render(make_report(),format="markdown")=="INTERNAL"
    assert calls==["html","markdown"]
    bad=make_report()
    bad["completeness"]["findings_verified"]=42
    with pytest.raises(ValueError,match="FINDING_COMPLETENESS_FORGED"):
        guarded_enterprise_report_render(bad,format="html")
    assert calls==["html","markdown"]


def test_cli_fail_closed_without_explicit_readonly(tmp_path,capsys):
    from scripts.preview_enterprise_report_evidence_readonly import main
    assert main([],repo_root=tmp_path)==2
    answer=json.loads(capsys.readouterr().out)
    assert answer["status"]=="HOLD_EXPLICIT_READ_ONLY_REQUIRED"
    assert not list(tmp_path.iterdir())
