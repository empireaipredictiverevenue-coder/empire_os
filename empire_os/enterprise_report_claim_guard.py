"""Fail-closed evidence-claim contract for EmpireOS enterprise draft rendering.

Use the guard *before* existing Markdown or HTML renderers. It validates the
nested report, count reconciliation, source-claim status, release governance,
and unverified nature of caller-provided findings. It never converts a
report into verified financial or commercial evidence.
"""
from __future__ import annotations

from collections import Counter,defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json,re

SCHEMA="empire.predictive_revenue.enterprise_diagnostic_report.v1"
GATE="empire.enterprise_report_pre_render_evidence_gate.v1"
CASE_RE=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,95}\Z")
SRC_RE=re.compile(r"(?:source|canonical):[^\s]{1,235}\Z")
MAX_FINDINGS=60
MIN_CHAPTERS=12
RELEASE_KEYS=(
    "original_client_records_verified","tenant_permissions_verified",
    "finance_reconciliation_signed","findings_source_audited",
    "human_report_reviewed","client_release_approved",
    "customer_delivery_enabled",
)
SOURCE_KEYS=(
    "original_customer_source_verified",
    "independent_financial_reconciliation_verified",
    "time_ordered_forecast_holdout_verified",
    "tenant_access_authorized_for_customer",
)
EXPECTED_SIGNOFFS={
    "Client-authorised data custodian":"PENDING_INDEPENDENT_REVIEW",
    "Finance reconciliation owner":"PENDING_INDEPENDENT_REVIEW",
    "Commercial operations owner":"PENDING_INDEPENDENT_REVIEW",
    "Empire AI founder release gate":"PENDING_FOUNDER_RELEASE",
}
EXPECTED_TRUTH_KEYS=frozenset((
    "no_generic_growth_claims","no_unsupported_money_values",
    "no_fabricated_customers_or_outcomes",
    "each_finding_requires_cohort_denominator",
    "each_finding_requires_source_refs",
    "each_finding_requires_testable_alternative",
    "review_before_client_delivery",
))
EXEC_NONE_FLAGS=(
    "catalog_changed","new_os_or_database_created","production_activated",
    "financial_write","model_learning_promoted","outbound_enabled",
)


def _fail(reason:str)->None:
    raise ValueError("ENTERPRISE_REPORT_EVIDENCE_HOLD:"+reason)


def _bool_false(value:Any)->bool:
    return value is False


def _verify(report:Mapping[str,Any])->dict[str,Any]:
    if (not isinstance(report,Mapping)
            or report.get("schema_version")!=SCHEMA
            or report.get("report_disposition")!="INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE"
            or report.get("report_type")!="DETAILED_INTERNAL_EVIDENCE_REVIEW"
            or report.get("product_code")!="predictive_revenue_diagnostic"
            or report.get("mode")!="OBSERVE"
            or report.get("execution_authority")!="none"
            or any(report.get(k) is not False for k in EXEC_NONE_FLAGS)):
        _fail("NOT_AN_UNRELEASED_ENTERPRISE_DRAFT")
    ref=report.get("case_ref")
    if not isinstance(ref,str) or CASE_RE.fullmatch(ref) is None:
        _fail("NONPSEUDONYMOUS_CASE")
    try:
        when=datetime.fromisoformat(report["as_of_utc"].replace("Z","+00:00"))
    except (ValueError,AttributeError,KeyError,TypeError):
        _fail("INVALID_AS_OF_DATE")
    if when.utcoffset() is None:
        _fail("NAIVE_AS_OF_DATE")
    summary=report.get("executive_summary")
    if not isinstance(summary,Mapping) or summary.get("decision")!="HOLD_CUSTOMER_DIAGNOSTIC_CLAIMS":
        _fail("UNSAFE_EXECUTIVE_DECISION")
    for key in (
        "observed_client_revenue_cents",
        "verified_customer_opportunity_value_cents",
        "forecast_improvement_claim",
        "recommended_approved_spend_cents",
    ):
        if summary.get(key) is not None:
            _fail("UNVERIFIED_EXECUTIVE_MONEY_OR_FORECAST")
    release=report.get("release_gate")
    if not isinstance(release,Mapping) or any(
        release.get(key) is not False for key in RELEASE_KEYS
    ):
        _fail("SOURCELESS_RELEASE_AUTHORITY")
    trace=report.get("source_traceability")
    if (not isinstance(trace,Mapping)
            or trace.get("source_type")!="EXISTING_EMPIREOS_PRODUCT_WORKBENCH"
            or trace.get("workbench_schema")!="empire.predictive_revenue.product_workbench.v1"
            or any(trace.get(key) is not False for key in SOURCE_KEYS)
    ):
        _fail("SOURCE_TRACEABILITY_ESCALATED")
    source=report.get("source_extract_reconciliation")
    if not isinstance(source,Mapping) or any(
        source.get(key) is not False for key in (
            "recognized_revenue_daily_total_verified",
            "tenant_access_verified",
            "usable_in_customer_report_as_verified_actual",
        )
    ):
        _fail("UNRECONCILED_CUSTOMER_SOURCE_ASSERTED_VERIFIED")
    signoffs=report.get("required_reviewer_signoffs")
    if not isinstance(signoffs,list) or len(signoffs)!=4:
        _fail("MISSING_INDEPENDENT_REVIEWERS")
    roles=set()
    for row in signoffs:
        if (not isinstance(row,Mapping)
                or not isinstance(row.get("reviewer_role"),str)
                or row["reviewer_role"] in roles
                or row.get("decision")!=EXPECTED_SIGNOFFS.get(row["reviewer_role"])
                or row.get("verified_signature_ref") is not None):
            _fail("UNAUTHORIZED_SIGNOFF")
        roles.add(row["reviewer_role"])
    if roles!=set(EXPECTED_SIGNOFFS):
        _fail("MISSING_NAMED_INDEPENDENT_REVIEWERS")
    contract=report.get("no_ai_slop_contract")
    if (not isinstance(contract,Mapping)
            or set(contract)!=EXPECTED_TRUTH_KEYS
            or any(v is not True for v in contract.values())):
        _fail("SOURCE_TRUTH_GOVERNANCE_ABSENT")
    findings=report.get("finding_register")
    chapters=report.get("chapters")
    completeness=report.get("completeness")
    if (not isinstance(findings,list) or len(findings)>MAX_FINDINGS
            or not isinstance(chapters,list)
            or len(chapters)!=MIN_CHAPTERS
            or type(report.get("chapter_count")) is not int
            or report["chapter_count"]!=len(chapters)
            or not isinstance(completeness,Mapping)):
        _fail("INCOMPLETE_REPORT_INVENTORY")
    finding_ids=set()
    counts=Counter()
    reference_to_ids=defaultdict(set)
    for finding in findings:
        if not isinstance(finding,Mapping):
            _fail("MALFORMED_FINDING")
        fid=finding.get("finding_id")
        chapter=finding.get("chapter_key")
        if (not isinstance(fid,str) or not 1<=len(fid)<=65
                or fid in finding_ids
                or not isinstance(chapter,str) or not chapter):
            _fail("DUPLICATE_OR_INVALID_FINDING")
        finding_ids.add(fid)
        counts[chapter]+=1
        if (finding.get("evidence_status")!=
                "SOURCE_CUSTODY_AND_COHORT_NOT_INDEPENDENTLY_VERIFIED"
                or finding.get("automated_client_claim_allowed") is not False
                or finding.get("causal_conclusion_confirmed") is not False
                or finding.get("recovered_revenue_cents") is not None
                or finding.get("investment_return_confirmed") is not False):
            _fail("FINDING_ESCALATED_WITHOUT_PRIMARY_EVIDENCE")
        eligible=finding.get("eligible_population")
        affected=finding.get("affected_population")
        rate=finding.get("affected_rate_percent")
        if (type(eligible) is not int or type(affected) is not int
                or not 0<=affected<=eligible or eligible==0
                or type(rate) not in (int,float)
                or abs(rate-round(100*affected/eligible,2))>0.011):
            _fail("FINDING_COHORT_DENOMINATOR_INCONSISTENT")
        refs=finding.get("source_references_caller_supplied")
        if not isinstance(refs,list) or not 1<=len(refs)<=12 or any(
            not isinstance(source,str) or SRC_RE.fullmatch(source) is None
            for source in refs
        ):
            _fail("SOURCE_CLAIM_REFERENCE_INVALID")
        for source_ref in refs:
            reference_to_ids[source_ref].add(fid)
        scenario=finding.get("illustrative_contribution_scenario")
        if scenario is not None:
            if (not isinstance(scenario,Mapping)
                    or scenario.get("client_investment_return_proven") is not False):
                _fail("ILLUSTRATIVE_MODEL_PROMOTED_AS_ACTUAL")
            for source_ref in scenario.get(
                "assumption_source_refs_caller_supplied",[]
            ):
                if not isinstance(source_ref,str) or SRC_RE.fullmatch(source_ref) is None:
                    _fail("ILLUSTRATIVE_SOURCE_REFERENCE_INVALID")
                reference_to_ids[source_ref].add(fid)
    chapter_keys=set()
    for chapter in chapters:
        if not isinstance(chapter,Mapping):
            _fail("INVALID_CHAPTER")
        key=chapter.get("chapter_key")
        if (not isinstance(key,str) or key in chapter_keys
                or type(chapter.get("finding_count")) is not int
                or chapter["finding_count"]!=counts[key]
                or chapter.get("source_evidence_complete") is not False
                or chapter.get("client_claim_approved") is not False
                or chapter.get("decision_quality")!="INVESTIGATION_REQUIRED"):
            _fail("CHAPTER_INTEGRITY_OR_VERIFICATION_ESCALATION")
        chapter_keys.add(key)
        source_state=chapter.get("existing_source_snapshots_present_not_verified")
        if (not isinstance(source_state,Mapping)
                or any(type(v) is not bool for v in source_state.values())):
            _fail("CHAPTER_SOURCE_SNAPSHOT_STATE_UNTRUSTED")
        entries=chapter.get("specific_claims_submitted_for_review")
        if (not isinstance(entries,list)
                or entries!=[f for f in findings if f["chapter_key"]==key]):
            _fail("CHAPTER_FINDING_LIST_MISMATCH")
    if not set(counts).issubset(chapter_keys):
        _fail("FINDING_WITHOUT_VALID_CHAPTER")
    if (type(completeness.get("chapters")) is not int
            or completeness["chapters"]!=len(chapters)
            or type(completeness.get("chapters_with_submitted_findings")) is not int
            or completeness["chapters_with_submitted_findings"]!=sum(
                counts[key]>0 for key in chapter_keys
            )
            or completeness.get("chapters_without_submitted_findings")!=[
                c["chapter_key"] for c in chapters if counts[c["chapter_key"]]==0
            ]
            or type(completeness.get("findings_unverified")) is not int
            or completeness["findings_unverified"]!=len(findings)
            or completeness.get("findings_verified")!=0
            or completeness.get("claims_approved_for_customer_report")!=0):
        _fail("FINDING_COMPLETENESS_FORGED")
    appendix=report.get("evidence_appendix")
    if not isinstance(appendix,list) or len(appendix)!=len(reference_to_ids):
        _fail("MISSING_OR_INFLATED_SOURCE_APPENDIX")
    observed_refs=set()
    for row in appendix:
        if not isinstance(row,Mapping):
            _fail("INVALID_SOURCE_APPENDIX")
        source_ref=row.get("source_ref")
        if (not isinstance(source_ref,str)
                or source_ref in observed_refs
                or SRC_RE.fullmatch(source_ref) is None
                or row.get("used_by_findings")!=sorted(reference_to_ids[source_ref])
                or row.get("original_record_read_by_this_report") is not False
                or row.get("tenant_scope_confirmed") is not False
                or row.get("source_integrity_verified") is not False
                or row.get("verification_state")!="SOURCE_REFERENCE_CLAIM_ONLY"):
            _fail("UNVERIFIED_SOURCE_REFERENCE_ASSERTED_VERIFIED")
        observed_refs.add(source_ref)
    if observed_refs!=set(reference_to_ids):
        _fail("SOURCE_APPENDIX_DOES_NOT_MATCH_FINDINGS")
    decisions=report.get("decision_register")
    if not isinstance(decisions,list) or len(decisions)!=len(findings):
        _fail("DECISION_COUNT_INFLATED")
    seen=set()
    for decision in decisions:
        if (not isinstance(decision,Mapping)
                or decision.get("finding_id") not in finding_ids
                or decision["finding_id"] in seen
                or decision.get("decision_status")!="PENDING_SOURCE_REVIEW_AND_OWNER_APPROVAL"
                or decision.get("spend_authorized") is not False):
            _fail("DECISION_UNSUPPORTED")
        seen.add(decision["finding_id"])
    if seen!=finding_ids:
        _fail("DECISION_MISSING_FINDING")
    return {
        "status":"INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED",
        "chapter_count":len(chapters),
        "unverified_finding_count":len(findings),
        "verified_finding_count":0,
        "original_source_record_verified_count":0,
        "customer_delivery_authorized":False,
        "external_reporting_authorized":False,
        "observed_at_utc":when.astimezone(timezone.utc).isoformat(),
        "source_reference_claim_only":True,
    }


def validate_enterprise_report_before_render(report:Mapping[str,Any])->dict[str,Any]:
    """Standalone validator; no caller authority, no side effects."""
    # Deep-copy prevents the caller changing nested report after validation.
    snapshot=deepcopy(report)
    detail=_verify(snapshot)
    digest=sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=True,
                             separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        "schema_version":GATE,
        **detail,
        "local_report_sha256":digest,
        "digest_is_publisher_signature":False,
        "underlying_finance_audited":False,
        "execution_authority":"none",
    }


def guarded_enterprise_report_render(report:Mapping[str,Any],*,format:str)->str:
    """Validate same immutable snapshot that reaches pre-existing renderer.

    The renderer module belongs to another agent and is imported only here.
    No route, shared DB or existing renderer is modified in this release.
    """
    snapshot=deepcopy(report)
    validate_enterprise_report_before_render(snapshot)
    if format=="markdown":
        from empire_os.predictive_revenue_enterprise_report import (
            render_enterprise_report_markdown,
        )
        return render_enterprise_report_markdown(snapshot)
    if format=="html":
        from empire_os.predictive_revenue_report_presentation import (
            render_enterprise_report_html,
        )
        return render_enterprise_report_html(snapshot)
    _fail("UNSUPPORTED_REPORT_RENDER_FORMAT")
