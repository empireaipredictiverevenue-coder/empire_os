"""Founder-only enterprise Predictive Revenue diagnostic report inside EmpireOS.

This is a detailed investigative *working report*. Inputs are scoped client
claims, not independently verified financial evidence. A completed sale,
client-facing delivery, confident causality, or reported actual revenue cannot
be inferred from caller flags. Human approval and original-source verification
are deliberately not supplied by this module.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
from math import isfinite
from pathlib import Path
from typing import Any
import re

from empire_os.predictive_revenue_product_workbench import (
    build_predictive_revenue_product_workbench,
)

# Each chapter must have a specific executive decision, measurement contract,
# falsification test and evidence gap. No chapter is considered a finding.
CHAPTERS: tuple[dict[str, Any], ...] = (
    {
        "key":"revenue_integrity",
        "title":"Recognised revenue and cash reconciliation",
        "executive_question":"Do orders, settlements and recognised revenue reconcile by accounting period?",
        "measures":("Recognised revenue by UTC period, currency and product",
                    "Order-to-settlement-to-recognition bridge",
                    "Recognised gross profit against source-backed actual costs",
                    "Refund, reversal, duplicate and deferred-recognition exceptions"),
        "source_keys":("revenue_pulse","economic_memory"),
        "tests":("Trace event IDs through original order and approved terms",
                 "Verify payment evidence, fulfilment and recognition cut-off",
                 "Reconcile cost evidence and double-count exposure"),
    },
    {
        "key":"pipeline_quality",
        "title":"Pipeline composition and conversion integrity",
        "executive_question":"Which specific stages lose qualified value, and is the stage definition consistent?",
        "measures":("Lead-to-qualified, qualified-to-opportunity and opportunity-to-win rates",
                    "Value-weighted stage ageing and stalled opportunities",
                    "Stage-to-stage cohort conversion, not mixed-period ratios"),
        "source_keys":("revenue_os","revenue_pulse"),
        "tests":("Compare stage definitions to immutable lifecycle events",
                 "Split created-period cohorts from closed-period cohorts",
                 "Inspect disqualifications, duplicates and missing owners"),
    },
    {
        "key":"revenue_leakage",
        "title":"Revenue leakage and preventable loss",
        "executive_question":"Which leakage mechanisms have attributable evidence rather than assumed lost sales?",
        "measures":("Abandoned qualified demand and age at abandonment",
                    "Unfollowed buyer questions and expired commercial offers",
                    "Failed delivery, expired terms and recoverable fulfilment gaps"),
        "source_keys":("revenue_pulse","economic_memory","commercial_exchange"),
        "tests":("Confirm the original revenue opportunity and event sequence",
                 "Exclude duplicate opportunities and non-buying intent",
                 "Distinguish recovered cash from modelled opportunity value"),
    },
    {
        "key":"sales_velocity",
        "title":"Sales-cycle velocity and bottleneck analysis",
        "executive_question":"Where does time accumulate between a qualified signal and settled revenue?",
        "measures":("Median and tail duration by stage and buyer cohort",
                    "Response latency by signal type and geography",
                    "Time to offer, approval, payment, delivery and recognition"),
        "source_keys":("revenue_os","revenue_pulse"),
        "tests":("Time-order events using one timezone and deduplicated IDs",
                 "Separate censored open cases from completed cycles",
                 "Identify changes in mix before attributing delay"),
    },
    {
        "key":"demand_and_market",
        "title":"Market demand, channel fit and addressable opportunity",
        "executive_question":"Where is verifiable demand strongest relative to capacity and competition?",
        "measures":("Qualified buying signals by segment and location",
                    "Observed demand-to-capacity mismatch",
                    "Opportunity concentration, freshness and source coverage"),
        "source_keys":("opportunity_loop","buyer_acquisition","commercial_exchange"),
        "tests":("Deduplicate signals and cross-check original publication date",
                 "Separate inferred market size from actual purchase intent",
                 "Segment by territory, product, buying constraints and season"),
    },
    {
        "key":"customer_economics",
        "title":"Unit economics, margins and contribution quality",
        "executive_question":"Which products and customer segments create positive realised contribution?",
        "measures":("Verified unit contribution and actual servicing costs",
                    "Acquisition cost by source, qualified buyer and closed account",
                    "Payback period, margin distribution and sensitivity"),
        "source_keys":("revenue_pulse","economic_memory","commercial_catalog"),
        "tests":("Use observed cost invoices and attributed orders",
                 "Check blended acquisition cost against channel-level cohorts",
                 "Keep estimated lifetime value separate from booked cash"),
    },
    {
        "key":"retention_and_ltv",
        "title":"Retention, repeat purchases and lifetime value",
        "executive_question":"Are renewal and lifetime-value assumptions supported by complete customer cohorts?",
        "measures":("Logo and net-revenue retention by acquisition cohort",
                    "Repeat-purchase interval and expansion versus contraction",
                    "Observed contribution LTV, horizon and right-censoring"),
        "source_keys":("economic_memory","revenue_pulse"),
        "tests":("Resolve customer identity consistently across orders",
                 "Treat incomplete cohorts as censored, not retained",
                 "Separate forecast LTV from observed contribution"),
    },
    {
        "key":"forecast_validation",
        "title":"Forecast quality, calibration and model limits",
        "executive_question":"Does the forecast outperform a pre-specified baseline on later verified outcomes?",
        "measures":("Horizon-specific absolute and relative error",
                    "Calibration against observed outcomes and naive baselines",
                    "Sample size, coverage, drift and temporal holdout results"),
        "source_keys":("predictive_cloud","predictive_intelligence","economic_memory"),
        "tests":("Pin every prediction before the associated outcome",
                 "Compare target dates, tenant and dimension custody",
                 "Exclude synthetic, modified, leaked or non-final actuals"),
    },
    {
        "key":"capacity_and_fulfilment",
        "title":"Delivery capacity, service quality and revenue at risk",
        "executive_question":"Does qualified demand exceed the capacity to fulfil verified commercial commitments?",
        "measures":("Committed versus available delivery capacity",
                    "Fulfilment latency, failed delivery and rejection rates",
                    "Capacity-constrained contribution by product and territory"),
        "source_keys":("buyer_capacity","commercial_exchange","revenue_pulse"),
        "tests":("Trace capacity claims to buyer-confirmed constraints",
                 "Compare promised SLA to fulfilment events",
                 "Exclude unavailable or non-compliant inventory"),
    },
    {
        "key":"data_lineage",
        "title":"Data reliability, provenance and control gaps",
        "executive_question":"Which broken identities or controls prevent a defensible management decision?",
        "measures":("Source freshness, ownership and tenant isolation",
                    "Missing source IDs, duplicates and recognition reconciliation",
                    "Audit completeness and unauthorised data movement"),
        "source_keys":("predictive_cloud","economic_memory","revenue_pulse"),
        "tests":("Inspect original reference identity and source timestamps",
                 "Test tenant separation and late-arrival correction paths",
                 "Verify restricted reader role and independent source custody"),
    },
    {
        "key":"risk_and_scenarios",
        "title":"Downside exposure, scenarios and assumptions",
        "executive_question":"Which adverse assumptions change the proposed investment decision?",
        "measures":("Revenue-at-risk ranges under explicit assumptions",
                    "Concentration by buyer, product, location and channel",
                    "Downside, base and upside *modelled* cases"),
        "source_keys":("economic_memory","predictive_cloud"),
        "tests":("Document baseline inputs and sensitivity directions",
                 "Bound scenario ranges to observed denominators",
                 "Avoid claiming scenario values as guaranteed recovery"),
    },
    {
        "key":"executive_execution",
        "title":"Decision register, implementation roadmap and proof of value",
        "executive_question":"Who must make which decision, by when, and what test proves it worked?",
        "measures":("Owner and accountable approver per action",
                    "Milestone target, dependency, budget and decision date",
                    "Baseline and post-change proof metric"),
        "source_keys":("astra","revenue_pulse"),
        "tests":("Check evidence, cost, owner and expected causal pathway",
                 "Separate 0-30, 31-60 and 61-90 day workstreams",
                 "Require a documented stop condition for each experiment"),
    },
)

CHAPTER_INDEX={chapter["key"]:chapter for chapter in CHAPTERS}
REPORT_MIN_CHAPTERS=12
_ALLOWED_PRIORITIES=frozenset({"P0","P1","P2"})
_BANNED_PUFF=(
    "unlock growth","game-changing","revolutionary","skyrocket",
    "transform your business","guaranteed roi","seamless growth",
)


def _valid_phrase(value:Any,field:str,*,limit:int=560)->str:
    if (not isinstance(value,str) or not value.strip()
        or len(value)>limit or "\n" in value or "\r" in value):
        raise ValueError(f"report {field} must be a concrete bounded statement")
    normalized=value.strip()
    if any(phrase in normalized.lower() for phrase in _BANNED_PUFF):
        raise ValueError(f"report {field} contains unsupported promotional language")
    if re.search(r"<[a-z!/]",normalized,re.IGNORECASE):
        raise ValueError(f"report {field} contains markup")
    return normalized


def _references(items:Any)->list[str]:
    if (type(items) not in (tuple,list) or not 1<=len(items)<=12):
        raise ValueError("source reference list must be bounded and nonempty")
    result=[]
    for item in items:
        ref=_valid_phrase(item,"source_ref",limit=240)
        if not (ref.startswith("canonical:") or ref.startswith("source:")):
            raise ValueError("report source references must be scoped")
        if ref in result:
            raise ValueError("duplicate report source reference")
        result.append(ref)
    return result


def _date(value:Any)->date:
    if type(value) is not str:
        raise ValueError("report date must be a date string")
    try:
        parsed=date.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid report date") from None
    if parsed.isoformat()!=value:
        raise ValueError("noncanonical report date")
    return parsed


def _integer(value:Any,field:str,*,allow_zero:bool=True)->int:
    if type(value) not in (int,Decimal):
        raise ValueError(f"report {field} must be an exact integer")
    if isinstance(value,Decimal) and not value.is_finite():
        raise ValueError(f"report {field} not finite")
    if value<0 or int(value)!=value or value>9_000_000_000_000_000:
        raise ValueError(f"report {field} invalid")
    if value==0 and not allow_zero:
        raise ValueError(f"report {field} must be positive")
    return int(value)


def _review_impact_model(value:Any,*,affected_population:int)->dict[str,Any]:
    """Bounded what-if contribution model, NOT source-verified recovery."""
    if not isinstance(value,Mapping):
        raise ValueError("impact scenario requires explicit assumptions")
    low=_integer(value.get("case_recovery_min_bps"),"minimum recovery bps")
    high=_integer(value.get("case_recovery_max_bps"),"maximum recovery bps")
    if high>10000 or low>high:
        raise ValueError("scenario recovery bounds inconsistent")
    unit=_integer(value.get("unit_contribution_cents"),
                  "assumed contribution per conversion",allow_zero=False)
    basis=_valid_phrase(value.get("contribution_basis"),"contribution_basis")
    exclusions=_valid_phrase(value.get("exclusions"),"exclusions")
    sources=_references(value.get("assumption_source_refs"))
    low_cases=(Decimal(affected_population)*Decimal(low)/10000).to_integral_value(
        rounding=ROUND_DOWN)
    high_cases=(Decimal(affected_population)*Decimal(high)/10000).to_integral_value(
        rounding=ROUND_DOWN)
    low_amount=int(low_cases)*unit
    high_amount=int(high_cases)*unit
    if high_amount>9_000_000_000_000_000:
        raise ValueError("scenario amount exceeds bounded precision")
    return {
        "scenario_status":"HYPOTHETICAL_NOT_VERIFIED",
        "case_recovery_min_bps":low,
        "case_recovery_max_bps":high,
        "assumed_unit_contribution_cents":unit,
        "assumption_basis":basis,
        "exclusions_and_confounds":exclusions,
        "assumption_source_refs_caller_supplied":sources,
        "modelled_case_count_range":[int(low_cases),int(high_cases)],
        "modelled_contribution_range_cents":[low_amount,high_amount],
        "actual_recovered_contribution_cents":None,
        "validated_unit_economics":False,
        "causal_uplift_demonstrated":False,
        "client_investment_return_proven":False,
        "formula":"floor(affected * recovery_bps / 10000) * assumed_unit_contribution_cents",
    }


def _review_finding(raw:Any,*,as_of:date)->dict[str,Any]:
    """Enforce specific, source-attributed investigation; never assert proof."""
    if not isinstance(raw,Mapping):
        raise ValueError("report finding must be an object")
    find_id=_valid_phrase(raw.get("finding_id"),"finding_id",limit=65)
    key=_valid_phrase(raw.get("chapter_key"),"chapter_key",limit=80)
    if key not in CHAPTER_INDEX:
        raise ValueError("report finding must map to a real chapter")
    start=_date(raw.get("window_start"))
    end=_date(raw.get("window_end"))
    if not start<=end<=as_of or (end-start).days>731:
        raise ValueError("report finding evidence period invalid")
    headline=_valid_phrase(raw.get("headline"),"headline",limit=180)
    signal=_valid_phrase(raw.get("observed_signal"),"observed_signal")
    metric=_valid_phrase(raw.get("measured_indicator"),"measured_indicator",limit=120)
    denominator=_integer(raw.get("eligible_population"),"eligible_population",
                         allow_zero=False)
    affected=_integer(raw.get("affected_population"),"affected_population")
    if affected>denominator:
        raise ValueError("affected population exceeds eligible cohort")
    # A single high-value deal is still worth investigation; a tiny cohort
    # cannot establish a reliable cross-client or forecast generalisation.
    priority=raw.get("priority")
    if priority not in _ALLOWED_PRIORITIES:
        raise ValueError("specific P0/P1/P2 triage category required")
    owner=_valid_phrase(raw.get("accountable_role"),"accountable_role",limit=120)
    root_cause=_valid_phrase(raw.get("causal_hypothesis"),"causal_hypothesis")
    recommended=_valid_phrase(raw.get("proposed_intervention"),
                              "proposed_intervention")
    test=_valid_phrase(raw.get("success_test"),"success_test")
    counter=_valid_phrase(raw.get("alternative_explanation"),
                          "alternative_explanation")
    sources=_references(raw.get("evidence_refs"))
    # No self-declared "verified" or "causal" flag from a case packet can
    # override source custody, full ledger finality or customer approval.
    return {
        "finding_id":find_id,
        "chapter_key":key,
        "headline":headline,
        "observed_signal_caller_supplied_unverified":signal,
        "measured_indicator":metric,
        "cohort_start":start.isoformat(),
        "cohort_end":end.isoformat(),
        "eligible_population":denominator,
        "affected_population":affected,
        "affected_rate_percent":round(100*affected/denominator,2),
        "small_sample_no_generalisation":denominator<10,
        "priority_proposed":priority,
        "accountable_role":owner,
        "causal_hypothesis_not_confirmed":root_cause,
        "alternative_explanation_to_test":counter,
        "proposed_intervention_pending_approval":recommended,
        "success_test":test,
        "source_references_caller_supplied":sources,
        "evidence_status":"SOURCE_CUSTODY_AND_COHORT_NOT_INDEPENDENTLY_VERIFIED",
        "causal_conclusion_confirmed":False,
        "recovered_revenue_cents":None,
        "investment_return_confirmed":False,
        "illustrative_contribution_scenario":(
            _review_impact_model(raw["illustrative_impact_model"],
                                 affected_population=affected)
            if raw.get("illustrative_impact_model") is not None else None
        ),
        "automated_client_claim_allowed":False,
    }


def _chapter_payload(spec:Mapping[str,Any], findings:Sequence[Mapping[str,Any]],
                     availability:Mapping[str,Any])->dict[str,Any]:
    keys=tuple(spec["source_keys"])
    source_state={}
    for key in keys:
        source_state[key]=availability.get(key,False) is True
    section_findings=[dict(value) for value in findings
                      if value["chapter_key"]==spec["key"]]
    return {
        "chapter_key":spec["key"],
        "title":spec["title"],
        "executive_decision_to_support":spec["executive_question"],
        "measurement_contract":list(spec["measures"]),
        "existing_empireos_source_keys":list(keys),
        "existing_source_snapshots_present_not_verified":source_state,
        "original_source_audit_tests":list(spec["tests"]),
        "specific_claims_submitted_for_review":section_findings,
        "finding_count":len(section_findings),
        "source_evidence_complete":False,
        "decision_quality":"INVESTIGATION_REQUIRED",
        "client_claim_approved":False,
    }


def build_enterprise_diagnostic_report(
    repo_root:Path, *,
    case:Mapping[str,Any]|None=None,
    as_of:datetime|None=None,
)->dict[str,Any]:
    """Assemble a detailed, explicitly INTERNAL report on existing EmpireOS.

    If case data is absent, return an extensive due-diligence workplan.
    If case data is supplied, use only bounded, clearly *unverified* claims.
    The case packet cannot confer verified status by calling itself verified.
    """
    when=as_of or datetime.now(timezone.utc)
    if not isinstance(when,datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("report as_of requires timezone")
    now=when.astimezone(timezone.utc)
    if case is not None and not isinstance(case,Mapping):
        raise ValueError("report case must be an object")
    supplied=case if case is not None else {}
    case_ref=supplied.get("case_ref","PRE_ENROLMENT_SOURCE_AUDIT")
    case_ref=_valid_phrase(case_ref,"case_ref",limit=96)
    # Case reference is internal, never a company name, mail or wallet address.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,95}",case_ref):
        raise ValueError("pseudonymous case_ref required")
    raw_findings=supplied.get("findings",[])
    if type(raw_findings) not in (tuple,list) or len(raw_findings)>60:
        raise ValueError("bounded finding inventory required")
    findings=[_review_finding(item,as_of=now.date()) for item in raw_findings]
    ids=[item["finding_id"] for item in findings]
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate report finding IDs")
    # The product workbench is the existing read interface. No independent
    # data ingestion, ETL, agent, client database, paid tool or model call.
    workbench=build_predictive_revenue_product_workbench(
        Path(repo_root),product_code="predictive_revenue_diagnostic",
        as_of=now)
    if workbench["existing_catalog_deployment_price_cents"]!=2_500_000:
        raise ValueError("approved catalog drift")
    from empire_os.predictive_revenue_demo import _source_state
    _,status=_source_state(Path(repo_root))
    available={key:row.get("available") is True for key,row in status.items()}
    pi=Path(repo_root)/"runtime/predictive_intelligence/latest.json"
    from empire_os.predictive_revenue_demo import _read_json
    available["predictive_intelligence"]=bool(_read_json(pi))
    # Optional client-source reconciliation remains subset-only and untrusted.
    # This deliberately does not create a data-import API or grant tenant access.
    source_extract=supplied.get("source_extract")
    if source_extract is None:
        source_review={
            "status":"NO_AUTHORISED_CUSTOMER_SOURCE_EXTRACT_SUBMITTED",
            "recognized_revenue_daily_total_verified":False,
            "tenant_access_verified":False,
            "source_subset_recognized_amount_cents":None,
            "usable_in_customer_report_as_verified_actual":False,
        }
    else:
        from empire_os.predictive_revenue_report_source_reconciliation import (
            reconcile_report_revenue_extract,
        )
        if not isinstance(source_extract,Mapping):
            raise ValueError("case source_extract must be a scoped mapping")
        source_review=reconcile_report_revenue_extract(
            tenant_id=source_extract.get("tenant_id"),
            day_utc=_date(source_extract.get("day_utc")),
            as_of=now,
            events=source_extract.get("events"),
            orders=source_extract.get("orders"),
        )
    sections=[_chapter_payload(item,findings,available) for item in CHAPTERS]
    submitted=sorted(findings,key=lambda item:
                     (item["priority_proposed"],item["finding_id"]))
    completeness={
        "chapters":len(CHAPTERS),
        "chapters_with_submitted_findings":sum(
            bool(section["finding_count"]) for section in sections),
        "chapters_without_submitted_findings":[
            section["chapter_key"] for section in sections
            if section["finding_count"]==0],
        "findings_unverified":len(submitted),
        "findings_verified":0,
        "claims_approved_for_customer_report":0,
    }
    evidence_index={}
    for finding in submitted:
        refs=list(finding["source_references_caller_supplied"])
        scenario=finding.get("illustrative_contribution_scenario")
        if scenario:
            refs.extend(scenario["assumption_source_refs_caller_supplied"])
        for source in refs:
            evidence_index.setdefault(source,set()).add(finding["finding_id"])
    evidence_appendix=[
        {
            "source_ref":source,
            "used_by_findings":sorted(references),
            "original_record_read_by_this_report":False,
            "tenant_scope_confirmed":False,
            "source_integrity_verified":False,
            "verification_state":"SOURCE_REFERENCE_CLAIM_ONLY",
        }
        for source,references in sorted(evidence_index.items())
    ]
    decision_register=[
        {
            "finding_id":finding["finding_id"],
            "triage_priority":finding["priority_proposed"],
            "accountable_role":finding["accountable_role"],
            "proposed_intervention":finding[
                "proposed_intervention_pending_approval"],
            "hypothesis_falsification":finding[
                "alternative_explanation_to_test"],
            "acceptance_test":finding["success_test"],
            "evidence_prerequisite":"ORIGINAL_SOURCE_RECORDS_AND_COHORT_RECONCILIATION",
            "decision_status":"PENDING_SOURCE_REVIEW_AND_OWNER_APPROVAL",
            "spend_authorized":False,
        }
        for finding in submitted
    ]
    return {
        "schema_version":"empire.predictive_revenue.enterprise_diagnostic_report.v1",
        "product_code":"predictive_revenue_diagnostic",
        "report_title":"Predictive Revenue — Enterprise Diagnostic",
        "report_type":"DETAILED_INTERNAL_EVIDENCE_REVIEW",
        "report_version":"1.0-draft",
        "case_ref":case_ref,
        "as_of_utc":now.isoformat(),
        "product_price_cents_from_existing_catalog":2_500_000,
        "currency":"USD",
        "report_disposition":"INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE",
        "executive_summary":{
            "decision":"HOLD_CUSTOMER_DIAGNOSTIC_CLAIMS",
            "evidence_message":"Insufficient independent client-specific source custody to certify quantified findings.",
            "immediate_priority":"Obtain original customer source records, scoped authority and a source-to-ledger reconciliation.",
            "observed_client_revenue_cents":None,
            "verified_customer_opportunity_value_cents":None,
            "forecast_improvement_claim":None,
            "recommended_approved_spend_cents":None,
        },
        "source_traceability":{
            "source_type":"EXISTING_EMPIREOS_PRODUCT_WORKBENCH",
            "workbench_schema":workbench["schema_version"],
            "diagnostic_input_status":
                workbench["diagnostic_evidence_review"]["status"],
            "original_customer_source_verified":False,
            "independent_financial_reconciliation_verified":False,
            "time_ordered_forecast_holdout_verified":False,
            "tenant_access_authorized_for_customer":False,
        },
        "chapter_count":len(CHAPTERS),
        "chapters":sections,
        "finding_register":submitted,
        "source_extract_reconciliation":source_review,
        "evidence_appendix":evidence_appendix,
        "decision_register":decision_register,
        "completeness":completeness,
        "implementation_roadmap":{
            "first_30_days":{
                "purpose":"Establish source custody, baselines and decision ownership",
                "tasks":(
                    "Secure scoped customer authorisation and original CRM, order, ledger and fulfilment extracts",
                    "Create the event-by-event recognised revenue and cost reconciliation",
                    "Define funnel stage denominators and closed-cohort boundaries",
                    "Agree named accountable roles and an evidence review meeting",
                ),
                "exit_test":"Original source IDs, tenant scope, reconciliation and baseline accepted by human reviewer",
                "status":"NOT_STARTED",
            },
            "days_31_to_60":{
                "purpose":"Validate the largest attributable blockers against comparable cohorts",
                "tasks":(
                    "Test top leakage and conversion hypotheses against source-level event histories",
                    "Compare frozen forecasts against later actuals and a naive baseline",
                    "Quantify only supported contribution ranges with assumptions and sensitivity",
                    "Approve a bounded intervention plan with stop conditions",
                ),
                "exit_test":"Independent reviewer accepts causal limitations, priority and measurement plan",
                "status":"NOT_STARTED",
            },
            "days_61_to_90":{
                "purpose":"Measure controlled changes before scaling or expansion",
                "tasks":(
                    "Run limited approved operational interventions through existing EmpireOS governance",
                    "Capture pre/post outcome measures and external confounders",
                    "Reconcile realised value separately from projected uplift",
                    "Present the enterprise expansion decision with recorded uncertainty",
                ),
                "exit_test":"Source-backed post-intervention comparison and signed decision register",
                "status":"NOT_STARTED",
            },
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
                "reviewer_role":"Client-authorised data custodian",
                "signoff_scope":"Tenant authority, source identity, record coverage, late-arrival policy",
                "decision":"PENDING_INDEPENDENT_REVIEW",
                "verified_signature_ref":None,
            },
            {
                "reviewer_role":"Finance reconciliation owner",
                "signoff_scope":"Payment, fulfilment, recognition cut-off, actual margin and reversals",
                "decision":"PENDING_INDEPENDENT_REVIEW",
                "verified_signature_ref":None,
            },
            {
                "reviewer_role":"Commercial operations owner",
                "signoff_scope":"Funnel denominators, hypotheses, intervention accountability and test plan",
                "decision":"PENDING_INDEPENDENT_REVIEW",
                "verified_signature_ref":None,
            },
            {
                "reviewer_role":"Empire AI founder release gate",
                "signoff_scope":"Final report claims, scope, customer permissions and delivery authority",
                "decision":"PENDING_FOUNDER_RELEASE",
                "verified_signature_ref":None,
            },
        ],
        "no_ai_slop_contract":{
            "no_generic_growth_claims":True,
            "no_unsupported_money_values":True,
            "no_fabricated_customers_or_outcomes":True,
            "each_finding_requires_cohort_denominator":True,
            "each_finding_requires_source_refs":True,
            "each_finding_requires_testable_alternative":True,
            "review_before_client_delivery":True,
        },
        "catalog_changed":False,
        "new_os_or_database_created":False,
        "production_activated":False,
        "financial_write":False,
        "model_learning_promoted":False,
        "outbound_enabled":False,
        "mode":"OBSERVE",
        "execution_authority":"none",
    }


def render_enterprise_report_markdown(report:Mapping[str,Any])->str:
    """Long-form analyst draft. No generic copy or fabricated results."""
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=
           "empire.predictive_revenue.enterprise_diagnostic_report.v1"
        or report.get("report_disposition")!=
           "INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE"
        or report.get("release_gate",{}).get("customer_delivery_enabled") is not False):
        raise ValueError("enterprise report preview must be unreleased")
    sections=report.get("chapters")
    if type(sections) is not list or len(sections)!=REPORT_MIN_CHAPTERS:
        raise ValueError("full diagnostic chapter inventory required")
    lines=[
        "# Predictive Revenue — Enterprise Diagnostic",
        "",
        "**INTERNAL WORKING DRAFT — NOT VERIFIED FOR CUSTOMER DELIVERY**",
        "",
        f"Case reference: `{report['case_ref']}`",
        f"As-of: {report['as_of_utc']} (UTC)",
        "Product: Empire AI Predictive Revenue Diagnostic (existing EmpireOS product)",
        "",
        "## 1. Executive decision and limitations",
        "",
        "**Decision:** HOLD customer-facing diagnostic claims until original-source evidence is independently reviewed.",
        "",
        "This is an investigation and evidence-requirements report, not a completed",
        "financial audit, guaranteed savings forecast, verified root-cause",
        "finding, or signed investment case. Blank evidence cannot be scored",
        "as zero leakage, zero opportunity or zero recognised revenue.",
        "",
        "Required approvals: authorised client data scope; independent source",
        "custody; accounting reconciliation; reviewed financial assumptions;",
        "and explicit human release of the final client deliverable.",
        "",
        "## 2. Evidence inventory and quantified-findings register",
        "",
        f"Investigative chapters: **{report['chapter_count']}**.",
        f"Submitted, not independently verified, findings: **{report['completeness']['findings_unverified']}**.",
        f"Verified client-facing findings: **{report['completeness']['findings_verified']}**.",
        "No actual revenue, recovered revenue, forecast improvement or ROI",
        "is asserted from the existing runtime snapshots.",
        "",
    ]
    source_review=report["source_extract_reconciliation"]
    lines.extend((
        "### Source extract reconciliation (supplied subset only)",
        "",
        f"- Source status: {source_review['status']}",
        "- Original source completeness: NOT VERIFIED.",
        "- Independent tenant authorisation: NOT VERIFIED.",
        "- Official recognised revenue total: NOT ESTABLISHED.",
        "",
    ))
    crm_review=report.get("existing_crm_observation_review")
    if crm_review is not None:
        if (not isinstance(crm_review,Mapping)
            or crm_review.get("schema_version")!=
                "empire.predictive_revenue.crm_case_observation.v1"
            or crm_review.get("customer_delivery_enabled") is not False
            or crm_review.get("snapshot_is_full_tenant_census") is not False):
            raise ValueError("untrusted CRM source observation")
        obs=crm_review.get("bounded_observations")
        if (not isinstance(obs,Mapping)
            or any(type(obs.get(key)) is not int or obs[key]<0
                   for key in ("observed_records",
                               "conversation_reference_missing",
                               "buyer_reference_missing",
                               "quoted_price_absent_or_zero_records",
                               "deal_probability_missing_records"))):
            raise ValueError("CRM metrics not available")
        lines.extend((
            "### Tenant-scoped Revenue CRM snapshot — internal observation only",
            "",
            f"- CRM source status: {crm_review['status']}",
            f"- Records in bounded view: {obs['observed_records']}",
            f"- Without conversation reference: {obs['conversation_reference_missing']}",
            f"- Without buyer reference: {obs['buyer_reference_missing']}",
            f"- Without a positive listed price: {obs['quoted_price_absent_or_zero_records']}",
            f"- Without deal-probability input: {obs['deal_probability_missing_records']}",
            "- Original dataset completeness, conversion rates and financial finality: NOT VERIFIED.",
            "",
        ))
    if not report["finding_register"]:
        lines+=(
            "**No client finding has yet met independent-source requirements.**",
            "The section-by-section questions below are the exact due-diligence",
            "scope; they are not claims that a client has these problems.",
            "",
        )
    else:
        for finding in report["finding_register"]:
            lines+=(
                f"### {finding['finding_id']} — {finding['headline']}",
                "",
                f"- Chapter: {finding['chapter_key']} | Proposed triage: {finding['priority_proposed']}",
                f"- Indicator: {finding['measured_indicator']}",
                f"- Supplied cohort: {finding['cohort_start']} to {finding['cohort_end']}",
                f"- Supplied rate: {finding['affected_population']} / {finding['eligible_population']} ({finding['affected_rate_percent']}%)",
                f"- Observed signal (unverified): {finding['observed_signal_caller_supplied_unverified']}",
                f"- Suspected mechanism, NOT established causation: {finding['causal_hypothesis_not_confirmed']}",
                f"- Competing explanation to test: {finding['alternative_explanation_to_test']}",
                f"- Proposed corrective step (requires review): {finding['proposed_intervention_pending_approval']}",
                f"- Accountable role: {finding['accountable_role']}",
                f"- Success test: {finding['success_test']}",
                f"- Source references, as supplied: {', '.join(finding['source_references_caller_supplied'])}",
                "- Independent source-verification status: **NOT VERIFIED**.",
                "- Recovered revenue and investment return: **NOT ESTABLISHED**.",
                "",
            )
            if finding.get("small_sample_no_generalisation"):
                lines.append("- **Small cohort:** observation only; do not generalise its rate.")
            scenario=finding.get("illustrative_contribution_scenario")
            if scenario:
                lines.extend((
                    "**ILLUSTRATIVE CONTRIBUTION — not verified recovery**",
                    f"- Hypothesised recovery range: {scenario['case_recovery_min_bps']}–{scenario['case_recovery_max_bps']} basis points of affected cases.",
                    f"- Modelled additional cases: {scenario['modelled_case_count_range'][0]}–{scenario['modelled_case_count_range'][1]}.",
                    f"- Assumed contribution per case: {scenario['assumed_unit_contribution_cents']} cents.",
                    f"- Modelled contribution range: {scenario['modelled_contribution_range_cents'][0]}–{scenario['modelled_contribution_range_cents'][1]} cents.",
                    f"- Contribution basis: {scenario['assumption_basis']}.",
                    f"- Exclusions: {scenario['exclusions_and_confounds']}.",
                    f"- Supplied assumption sources: {', '.join(scenario['assumption_source_refs_caller_supplied'])}.",
                    f"- Formula: {scenario['formula']}.",
                    "- No verified causal uplift, realised revenue, recovered contribution or investment return.",
                    "",
                ))
    lines+=["## 3. Detailed investigation by business function",""]
    for index,section in enumerate(sections,start=1):
        lines.extend((
            f"### 3.{index} {section['title']}",
            "",
            f"**Executive decision:** {section['executive_decision_to_support']}",
            "",
            "**Exact measurement requirements**",
            "",
        ))
        lines.extend(f"- {metric}" for metric in section["measurement_contract"])
        lines+=["","**Original-source and hypothesis checks**",""]
        lines.extend(f"- {item}" for item in section["original_source_audit_tests"])
        lines+=["","**Existing EmpireOS input availability (not proof)**",""]
        for key,seen in section["existing_source_snapshots_present_not_verified"].items():
            lines.append(f"- `{key}`: {'snapshot exists; original evidence unverified' if seen else 'snapshot missing'}")
        lines.extend((
            "",
            f"Submitted items to review: {section['finding_count']}; "
            "independently verified: 0.",
            "**Disposition:** evidence work required before an executive conclusion.",
            "",
        ))
    lines+=["## 4. Risk register and credibility checks",""]
    lines+=(
        "- Revenue-recognition versus cash-settlement timing must be reconciled separately.",
        "- Cohort denominators, incomplete cases and calendar cuts must be auditable.",
        "- Correlation in pipeline behaviour is not proof of causality.",
        "- Forecast error must be compared with a simple pre-registered baseline.",
        "- Risk, margin and recovered revenue must not use the same dollar twice.",
        "- Simulation or synthetic scientific-agent performance is not real customer evidence.",
        "- Unverified third-party estimates must not appear as audited market facts.",
        "- Proposed urgency is a triage category, not a mathematically calibrated confidence score.",
        "",
        "## 5. Execution and governance roadmap",
        "",
    )
    for period,label in (
        ("first_30_days","Days 0–30"),
        ("days_31_to_60","Days 31–60"),
        ("days_61_to_90","Days 61–90"),
    ):
        node=report["implementation_roadmap"][period]
        lines.extend((f"### {label}: {node['purpose']}",""))
        lines.extend(f"- {task}" for task in node["tasks"])
        lines.extend((f"- **Acceptance test:** {node['exit_test']}",""))
    lines+=["## 6. Source evidence traceability appendix",""]
    if not report["evidence_appendix"]:
        lines+=["No original client source IDs have been submitted for independent review.",""]
    else:
        for evidence in report["evidence_appendix"]:
            lines.extend((
                f"- {evidence['source_ref']}: used in {', '.join(evidence['used_by_findings'])}",
                "  - Original record read: NO; tenant scope confirmed: NO; source integrity verified: NO.",
            ))
    lines+=["","## 7. Proposed owner and decision register",""]
    if not report["decision_register"]:
        lines+=["No intervention approved; complete the source-custody review first.",""]
    else:
        for decision in report["decision_register"]:
            lines.extend((
                f"- {decision['finding_id']} ({decision['triage_priority']}): {decision['proposed_intervention']}",
                f"  - Accountable role: {decision['accountable_role']}; independent acceptance test: {decision['acceptance_test']}",
                f"  - Competing explanation: {decision['hypothesis_falsification']}",
                "  - Status: PENDING SOURCE REVIEW AND OWNER APPROVAL; spend authorised: NO.",
            ))
    lines+=(
        "",
        "## 8. Decision record and delivery gate",
        "",
        "**Report status: INTERNAL DRAFT / NOT APPROVED FOR DELIVERY.**",
        "The eventual client version must include a reviewed source appendix,",
        "sample-selection logic, financial reconciliations, falsification",
        "tests, owner-assigned action plan, assumptions register and sign-offs.",
        "",
    )
    for gate,value in report["release_gate"].items():
        lines.append(f"- {gate.replace('_',' ')}: {'approved' if value else 'not approved'}")
    lines+=["", "### Independent reviewer requirements", ""]
    for review in report["required_reviewer_signoffs"]:
        lines.append(
            f"- {review['reviewer_role']}: {review['signoff_scope']} "
            f"— {review['decision']}"
        )
    lines+=("","No automated outbound, order, payment, recognition or model-weight actions were performed.","")
    return "\n".join(lines)
