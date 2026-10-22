"""Jev evidence gap between historical sector volume and actual client demand.

Existing Jev archive/GPS priority can choose where to *research*. Existing
Jev client pain/Intent Brain may propose which public statements to inspect.
Neither proves a first-party SaaS buyer or grants contact, CRM, financial
or data resale authority. Strict aggregate-only output.
"""
from __future__ import annotations
from collections import Counter
from typing import Any, Mapping

PRIORITY_SCHEMA="empire.jev.sector_research_priority.v1"
PAIN_SCHEMA="empire.jev.client_pain_discovery.v1"
SCHEMA="empire.jev.top_sector_demand_gap.v1"
TARGETS=("general_contractor","roofing","hvac")
REVIEWABLE=frozenset(("REVIEW_IDENTITY","REVIEW_PAIN_HYPOTHESIS"))
APPROVED_SOURCE_TYPES=frozenset({
    "reddit","linkedin","quora","company_site","public_rfp",
    "public_review","public_job_post","public_forum","first_party_intake",
})
WORK_TYPE="PUBLIC_CONTRACTOR_WORK_PROCUREMENT"
SERVICE_TYPE="B2B_LEAD_GENERATION_OR_SOFTWARE_NEED"
SOURCE_QUERY_FOCI={
    "general_contractor":(
        "general contractor owner needs qualified appointment pipeline",
        "general contractor founder needs consistent commercial project enquiries"),
    "roofing":(
        "roofing company owner asking for qualified roofing leads",
        "roofing contractor seeking help converting estimate requests"),
    "hvac":(
        "hvac service company owner needs qualified service appointments",
        "heating cooling business seeking help fixing missed inbound calls"),
}


def _count(x:Any,maximum:int=100_000)->int:
    if type(x) is not int or not 0<=x<=maximum:
        raise ValueError("untrusted evidence count")
    return x


def review_sector_demand_gap(
    sector_priority:Mapping[str,Any],
    public_pain:Mapping[str,Any], *,
    public_procurement_candidates:tuple[Mapping[str,Any],...] = (),
)->dict[str,Any]:
    if (not isinstance(sector_priority,Mapping)
        or sector_priority.get("schema_version")!=PRIORITY_SCHEMA
        or sector_priority.get("status")!="AUDITED_HISTORICAL_SECTOR_RESEARCH_QUEUE_ONLY"
        or sector_priority.get("mode")!="OBSERVE"
        or sector_priority.get("historical_archive_rows")!=32899
        or sector_priority.get("archive_id_set_matched") is not True
        or sector_priority.get("historical_record_count_is_not_current_prospect_count") is not True
        or sector_priority.get("verified_contactable_leads")!=0
        or sector_priority.get("outreach_sent")!=0
        or sector_priority.get("automatic_research_dispatch") is not False
        or sector_priority.get("database_writes") is not False
        or sector_priority.get("execution_authority")!="none"):
        raise ValueError("untrusted or commercially promoted sector priority")
    sector_rows=sector_priority.get("sector_research_rows")
    if not isinstance(sector_rows,list) or len(sector_rows)>80:
        raise ValueError("unbounded Jev sector review evidence")
    selected=[]
    for niche in TARGETS:
        matches=[x for x in sector_rows if isinstance(x,Mapping) and x.get("niche")==niche]
        if len(matches)!=1:
            raise ValueError("missing or duplicated original priority sector")
        row=matches[0]
        if (row.get("research_lane")!="CORROBORATE_RECENT_ORIGINAL_DEMAND"
            or row.get("scope")!="HISTORICAL_SECTOR_AGGREGATE"
            or row.get("current_contactable_records_verified") is not False
            or row.get("individual_qualified_leads")!=0
            or row.get("specific_buyer_buybox_verified") is not False
            or row.get("auto_contact_authority") is not False):
            raise ValueError("original niche not eligible for evidence-gap research")
        if (type(row.get("historical_prospect_rows")) is not int
            or not 0<row["historical_prospect_rows"]<=32899
            or type(row.get("recent_gps_observed_acquisitions_not_buyer_demand")) is not int
            or not 0<=row["recent_gps_observed_acquisitions_not_buyer_demand"]<=100000):
            raise ValueError("invalid archived or GPS counts")
        selected.append(row)

    if (not isinstance(public_pain,Mapping)
        or public_pain.get("schema_version")!=PAIN_SCHEMA
        or public_pain.get("mode")!="OBSERVE"
        or public_pain.get("status")!="CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY"
        or public_pain.get("prospects_verified")!=0
        or public_pain.get("buyer_purchase_intent_verified") is not False
        or public_pain.get("source_rights_and_consent_verified") is not False
        or public_pain.get("crm_writes") is not False
        or public_pain.get("outbound_sent")!=0
        or public_pain.get("execution_authority")!="none"):
        raise ValueError("untrusted actual client-demand evidence")
    items=public_pain.get("items")
    count=_count(public_pain.get("observations_submitted"),500)
    classified=_count(public_pain.get("observations_with_pain_or_topic"),500)
    if (not isinstance(items,list) or len(items)!=classified
        or classified>count):
        raise ValueError("incoherent real source pain observations")

    classified_lanes=Counter()
    seen=set()
    for item in items:
        if not isinstance(item,Mapping):
            raise ValueError("unsafe pain source item")
        # Hidden source hashes, URLs, person titles and original text are
        # intentionally excluded from downstream research packet.
        ref=item.get("source_sha256")
        if (not isinstance(ref,str) or len(ref)!=64
            or any(ch not in "0123456789abcdef" for ch in ref)
            or ref in seen
            or item.get("source") not in APPROVED_SOURCE_TYPES
            or item.get("unverified_identity") is not True
            or item.get("unverified_commercial_need") is not True
            or item.get("outreach_authorized") is not False
            or item.get("review_lane") not in (
                "REVIEW_IDENTITY","REVIEW_PAIN_HYPOTHESIS",
                "MONITOR_UNVERIFIED","NO_SOLICITATION",
                "EXCLUDE_NONBUYER")
            or "private_evidence_url" in item):
            raise ValueError("untrusted, promoted or private source record")
        seen.add(ref)
        classified_lanes[item["review_lane"]]+=1
    if dict(classified_lanes)!=public_pain.get("review_lane_counts"):
        raise ValueError("source review lane counts mismatch")

    # Public bid data denotes demand for FIELD WORK, not for a company to
    # purchase Jev / EmpireOS SaaS, marketing, data brokerage or PPC services.
    notices=[]
    if len(public_procurement_candidates)>6:
        raise ValueError("public procurement candidates must be bounded")
    seen_notice=set()
    for row in public_procurement_candidates:
        if not isinstance(row,Mapping):
            raise ValueError("invalid public procurement discovery record")
        key=row.get("notice_id")
        niche=row.get("sector")
        if (not isinstance(key,str) or len(key)>50
            or not key.isalnum()
            or key in seen_notice or niche not in TARGETS
            or row.get("opportunity_type")!=WORK_TYPE
            or row.get("source_original_notice_independently_inspected") is not False
            or row.get("contractor_bids_are_not_empire_saas_buyers") is not True
            or row.get("customer_outreach_authorized") is not False):
            raise ValueError("untrusted contractor procurement source candidate")
        seen_notice.add(key)
        notices.append({
            "sector":niche,"notice_id":key,
            "source_class":"SECONDARY_DISCOVERY_ORIGINAL_NOTICE_REVIEW_REQUIRED",
            "procurement_object":WORK_TYPE,
            "buyer_of_empire_leadgen_or_saas_verified":False,
            "bidding_eligibility_and_deadline_current_verified":False,
            "allowed_for_auto_outreach":False,
        })
    rows=[]
    for src in selected:
        niche=src["niche"]
        matches=[x for x in items if x.get("niche")==niche]
        potential=sum(x["review_lane"] in REVIEWABLE
                      and not x.get("no_solicitation",False)
                      for x in matches)
        held=sum(x.get("no_solicitation",False) for x in matches)
        rows.append({
            "sector":niche,
            "historical_prospect_rows":src["historical_prospect_rows"],
            "recent_acquisition_observations_not_demand":src[
                "recent_gps_observed_acquisitions_not_buyer_demand"],
            "classified_public_pain_observations":len(matches),
            "unverified_public_pain_review_candidates":potential,
            "no_solicitation_rows_held":held,
            "actual_b2b_software_or_leadgen_purchase_request_proven":False,
            "original_canonical_buyer_identity_verified":False,
            "verified_buyer_capacity":False,
            "next_existing_research_action":(
                "ORIGINAL_FIRST_PARTY_CLIENT_NEED_DISCOVERY_AND_EVIDENCE_REVIEW"),
            "required_original_contract":SERVICE_TYPE,
            "federal_procurement_not_equivalent_to_saas_purchase":True,
            "safe_to_contact":False,
        })
    discovery_briefs=[]
    for row in rows:
        discovery_briefs.append({
            "sector":row["sector"],
            "existing_owner":"research_original_source_and_buyer_scout",
            "research_queries":list(SOURCE_QUERY_FOCI[row["sector"]]),
            "permitted_source_type_review_scope":[
                "company_site","reddit","linkedin","public_forum",
                "first_party_intake"],
            "required_source_confirmation":(
                "original_authored_company_request_for_lead_generation_"
                "sales_conversion_or_software_purchase"),
            "must_reject":[
                "recruitment_job_post_as_purchase_intent",
                "vendor_marketing_pitch_as_buyer_need",
                "public_works_rfp_as_empire_saas_buyer",
                "historical_permit_as_current_homeowner_request",
                "opt_out_or_do_not_contact_message",
            ],
            "jurisdiction_geography_confirmed":False,
            "independent_identity_verified":False,
            "client_purchase_intent_verified":False,
            "consumer_data_or_contacts_to_extract":0,
            "outreach_allowed":False,
            "owner_review_required":True,
            "automatic_dispatch_authorized":False,
        })
    return {
        "schema_version":SCHEMA,
        "status":"TOP_THREE_SECTORS_HAVE_RESEARCH_GAPS_NOT_VERIFIED_BUYERS",
        "mode":"OBSERVE",
        "priority_sectors":list(TARGETS),
        "public_observations_submitted":count,
        "public_pain_or_topic_observations":classified,
        "public_pain_lanes":dict(sorted(classified_lanes.items())),
        "sector_demand_research":rows,
        "existing_owner_source_discovery_briefs":discovery_briefs,
        "contractor_work_procurement_discovery_candidates":notices,
        "original_procurement_notices_verified":0,
        "software_or_marketing_clients_verified":0,
        "public_source_editorial_admissions":0,
        "consumer_or_personal_contacts_extracted":0,
        "individual_prospects_promoted":0,
        "buyer_scout_capacity_matches_verified":0,
        "crm_writes":False,"outbound_sent":0,
        "external_jev_calls":0,"execution_authority":"none",
    }
