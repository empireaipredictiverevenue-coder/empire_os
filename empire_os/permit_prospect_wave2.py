"""Original EmpireOS Permit Intelligence: verified public prospect RESEARCH only.

First-party official company pages checked by founder-side research on
2026-10-24. This dataset records observable *service fit* NOT verified
interest, spending authority, active projects, customer signals or permission
to send. No scraper, no exported private contacts, no production CRM/DB.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any,Mapping

SCHEMA="empire.permit_data.first_party_contractor_prospect_wave2.v1"
RESEARCH_DATE="2026-10-24"
# Exact first-party companies/services from their websites; emails are
# *generic public routes only* and are NOT sufficient authority to send.
SOURCE_ROWS=(
    {
      "company":"Demar Plumbing / Fire Protection / Mechanical",
      "domain":"demarnyc.com",
      "contact":"https://demarnyc.com/contact-us/",
      "evidence":"https://demarnyc.com/about-us/",
      "generic_inbox":"info@demarnyc.com",
      "address":"147 Attorney St, New York, NY 10002",
      "borough_or_market":"Manhattan",
      "evidence_detail":"Dedicated new-construction and service divisions, DOB/FDNY inspections, fire protection",
      "value_insight":"Separate approved-application filings from actual issued-permit evidence in preconstruction research",
      "buyer_question":"Does your new-construction team spend time rechecking NYC filing stages before deciding what to investigate?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":True,
      "contact_route_note":"Use general business enquiry only after original CRM suppression; estimating address receives bid requests, not vendor pitches",
    },
    {
      "company":"Tri-State Fire Sprinklers",
      "domain":"tristatefiresprinklers.com",
      "contact":"https://tristatefiresprinklers.com/contact-us/",
      "evidence":"https://tristatefiresprinklers.com/projects/",
      "generic_inbox":"info@tristatefiresprinklers.com",
      "address":"1237 39th St, Brooklyn, NY 11218",
      "borough_or_market":"Brooklyn",
      "evidence_detail":"Design/installation of wet and dry sprinkler systems; published NYC construction portfolio",
      "value_insight":"Check the original DOB NOW observation date when comparing apparent construction project stages",
      "buyer_question":"When reviewing new-construction work, do you manually verify which filing stages have actually changed?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":False,
      "contact_route_note":"General public business inbox; online inspection/quote forms are customer-service forms, not a prospecting permission",
    },
    {
      "company":"M&D Fire Sprinkler",
      "domain":"mdfiresprinkler.com",
      "contact":"https://mdfiresprinkler.com/about/",
      "evidence":"https://mdfiresprinkler.com/about/",
      "generic_inbox":"office@mdfiresprinkler.com",
      "address":"1267 Utica Ave, Brooklyn, NY 11203",
      "borough_or_market":"Brooklyn",
      "evidence_detail":"Commercial/residential fire suppression, standpipes, retrofitting and NYC DOB/FDNY violation removal",
      "value_insight":"Differentiate unchanged applications and observed modifications from independently evidenced permit issuance",
      "buyer_question":"Does your team use DOB filing histories when deciding which retrofit or installation enquiries deserve a closer look?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":True,
      "contact_route_note":"Office address is a public service enquiry route; sales-owner relevance and opt-outs unverified",
    },
    {
      "company":"Standard Fire Suppression Corp",
      "domain":"standardfireny.com",
      "contact":"https://standardfireny.com/",
      "evidence":"https://standardfireny.com/",
      "generic_inbox":"info@standardfireny.com",
      "address":"750 Third Ave, New York, NY 10017",
      "borough_or_market":"Manhattan",
      "evidence_detail":"Dedicated new-system installation and inspections/FDNY compliance divisions in NYC",
      "value_insight":"A newly approved filing is not independently confirmed trade demand or an available contract",
      "buyer_question":"For new sprinkler installations, do you have a reliable way to spot genuine application-stage changes rather than unchanged records?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":True,
      "contact_route_note":"Generic first-party published inbox only; no validated lead owner or buyer interest",
    },
    {
      "company":"ABCO Peerless Sprinkler Corp",
      "domain":"abcopeerless.com",
      "contact":"https://www.abcopeerless.com/",
      "evidence":"https://www.abcopeerless.com/",
      "generic_inbox":"info@abcopeerless.com",
      "address":"50 Midland Ave, Hicksville, NY 11801",
      "borough_or_market":"Greater New York / Long Island",
      "evidence_detail":"Greater NYC full-service design, new installation, retrofits and fire-protection maintenance",
      "value_insight":"Review official NYC application status separately from property-reference validation before committing estimator time",
      "buyer_question":"Does your project research team track early NYC sprinkler applications separately from actual permit approvals?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":False,
      "contact_route_note":"First-party general inbox; no company interest established",
    },
    {
      "company":"NYC Fire Sprinkler Corp",
      "domain":"nyfiresprinkler.com",
      "contact":"https://nyfiresprinkler.com/contactus/",
      "evidence":"https://nyfiresprinkler.com/our-services/",
      "generic_inbox":"info@nyfiresprinkler.com",
      "address":"2635 Roberts Ave, Bronx, NY 10461",
      "borough_or_market":"Bronx",
      "evidence_detail":"Residential/commercial system design/installation, new construction, inspection and repair",
      "value_insight":"Confirm which DOB NOW filing has evidence of a first permit and which remains an application",
      "buyer_question":"For new installations, how does your team currently check whether an NYC filing has advanced since its first appearance?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":False,
      "contact_route_note":"Generic first-party public inbox; emergency number excluded, person-level suppression unknown",
    },
    {
      "company":"Sirina Fire Protection Corp",
      "domain":"sirinafire.com",
      "contact":"https://sirinafire.com/",
      "evidence":"https://sirinafire.com/",
      "generic_inbox":"info@sirinafire.com",
      "address":"450 7th Ave, Suite 506, New York, NY 10123",
      "borough_or_market":"Manhattan / NY Metro",
      "evidence_detail":"Commercial and industrial sprinkler engineering, installation, service; published commercial portfolio",
      "value_insight":"Source-stamped stage-change tracking is more defensible than counting permit applications as guaranteed jobs",
      "buyer_question":"Does your commercial fire-protection team use early filing history to guide project research or estimating priorities?",
      "construction_research_fit":True,"new_install_or_new_construction":True,"dob_fdny_relevance":False,
      "contact_route_note":"Published general business inbox, not a verified buyer route; no permission to send",
    },
    {
      "company":"Fire Protection Design, Inc",
      "domain":"fireprotectiondesign.net",
      "contact":"https://fireprotectiondesign.net/",
      "evidence":"https://fireprotectiondesign.net/",
      "generic_inbox":None,
      "address":"14 Denver Dr, New City, NY 10956",
      "borough_or_market":"NY Metro / Rockland County",
      "evidence_detail":"NYC-area commercial and residential fire sprinkler design and source-plan documentation",
      "value_insight":"Reconcile permit application stage with the actual approved-permit evidence before using it in design research",
      "buyer_question":"Do your designers spend time reviewing NYC filing-stage changes for incoming fire-suppression projects?",
      "construction_research_fit":True,"new_install_or_new_construction":False,"dob_fdny_relevance":False,
      "contact_route_note":"Company site offers enquiry form; a usable general business email is not independently confirmed",
    },
)

def _sha(v:Mapping[str,Any])->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),
                          allow_nan=False).encode()).hexdigest()

def build_wave2(*,buyer_decision:Mapping[str,Any],journey:Mapping[str,Any])->dict:
    if (not isinstance(buyer_decision,Mapping)
        or buyer_decision.get("schema_version")!="empire.permit_data.private_buyer_decision_board.v1"
        or buyer_decision.get("buyer_decision_sha256")!=_sha({
            k:v for k,v in buyer_decision.items() if k!="buyer_decision_sha256"})
        or buyer_decision.get("commercial_release")!="HOLD_BUYER_SOURCE_RIGHTS_CONTACT_PAYMENT"
        or buyer_decision.get("approved_contact_routes")!=0
        or buyer_decision.get("authenticated_buyer_responses")!=0
        or buyer_decision.get("collected_cash_usd")!="0.00"
        or buyer_decision.get("execution_authority")!="none"
        or buyer_decision.get("buyer_contact_or_interview_executed") is not False
        or buyer_decision.get("external_report_distribution_authorized") is not False
        or buyer_decision.get("payment_or_checkout_activated") is not False
        or buyer_decision.get("production_empiredb_writes")!=0
        or buyer_decision.get("smart_crm_writes")!=0):
        raise ValueError("untrusted_original_permit_sales_evidence")
    if (not isinstance(journey,Mapping)
        or journey.get("schema_version")!="empire.permit_data.value_first_buyer_signal_journey.v1"
        or journey.get("private_buyer_journey_sha256")!=_sha({
            k:v for k,v in journey.items() if k!="private_buyer_journey_sha256"})
        or journey.get("mode")!="PRIVATE_SIMULATED_CONVERSATION_SCENARIOS_ONLY"
        or journey.get("verified_reply_count")!=0
        or journey.get("outbound_sent") is not False
        or journey.get("payments_received_usd")!="0.00"
        or journey.get("source_sample_release_criteria",{}).get("sample_shared") is not False
        or journey.get("execution_authority")!="none"
        or journey.get("qualified_genuine_buyers")!=0
        or journey.get("buyer_facing_sample_sent") is not False
        or journey.get("price_quote_issued") is not False
        or journey.get("empiredb_writes")!=0
        or journey.get("smart_crm_writes")!=0
        or journey.get("astra_jobs_scheduled")!=0):
        raise ValueError("untrusted_original_value_first_protocol")
    used={x.get("domain") for x in buyer_decision.get("original_company_research_only",[])}
    assert len(used)==5
    domains=[x["domain"] for x in SOURCE_ROWS]
    if len(set(domains))!=len(domains) or used.intersection(domains):
        raise ValueError("wave2_must_be_nonduplicated_original_permit_company_research")
    cards=[]
    for row in SOURCE_ROWS:
        if (not row["contact"].startswith("https://")
            or not row["evidence"].startswith("https://")
            or not row["construction_research_fit"]
            or row["buyer_question"].count("?")!=1
            or "$" in row["buyer_question"]):
            raise ValueError("unsafe_or_unsubstantiated_prospect_row")
        # Transparent, explainable service-fit rubric, not purchase propensity:
        # specialized sprinkler/construction + new installation + official
        # DOB/FDNY relevance + generic public business channel.
        fit=(2 if row["construction_research_fit"] else 0)+(
            2 if row["new_install_or_new_construction"] else 0)+(
            1 if row["dob_fdny_relevance"] else 0)+(
            1 if row["generic_inbox"] is not None else 0)
        first=(
            "Hello "+row["company"]+" team,\n\n"
            "A free NYC DOB NOW research check: an approved application alone "
            "does not confirm an issued permit or an available construction "
            "contract. It's worth checking the exact reference and observation "
            "date before spending estimator time on it.\n\n"
            "Your published work includes "+row["evidence_detail"]+". "
            +row["buyer_question"]+"\n\n"
            "Email reply is fine; no call necessary. "
            "Please say if you prefer no further contact.\n\n"
            "Empire AI | Permit Intelligence\n"
        )
        card={
            **row,
            "source_review_day":RESEARCH_DATE,
            "evidence_source_type":"FIRST_PARTY_PUBLIC_COMPANY_WEBSITE_UNAUTHENTICATED_WEB_OBSERVATION",
            "objective_research_fit_points_not_buying_probability":fit,
            "fit_max_points":6,
            "first_touch_subject_unsent":"A useful NYC sprinkler filing check",
            "value_first_body_unsent":first,
            "first_touch_has_price_or_paid_offer":False,
            "no_first_touch_project_data_attachment":True,
            "confirmed_buyer_interest":False,
            "email_provider_reply_verified":False,
            "verified_company_procurement_need":False,
            "individual_recipient_identity_verified":False,
            "prior_original_smart_crm_suppression_cleared":False,
            "owner_send_authorized":False,
            "sample_distribution_rights_approved":False,
            "sample_requested_by_buyer":False,
            "free_sample_sent":False,
            "first_touch_sent":False,
            "eligible_to_send":False,
            "sales_status":"RESEARCH_FIT_NOT_BUYER_SIGNAL",
            "confidence_note":"First-party advertised services, not actual buyer intent or contractual work",
        }
        if first.count("?")!=1 or "$" in first or "@" in first:
            raise ValueError("first_contact_no_sales_pitch_or_contact_leak")
        cards.append(card)
    cards.sort(key=lambda r:(-r["objective_research_fit_points_not_buying_probability"],r["company"].lower()))
    packet={
        "schema_version":SCHEMA,
        "mode":"NEW_PUBLIC_PROSPECT_RESEARCH_ONLY_NO_OUTBOUND",
        "original_product":"ONE_EMPIREOS_PERMIT_INTELLIGENCE",
        "observed_public_company_websites_on":RESEARCH_DATE,
        "original_buyer_decision_sha256":buyer_decision["buyer_decision_sha256"],
        "original_value_first_journey_sha256":journey["private_buyer_journey_sha256"],
        "original_five_company_count_unchanged":len(used),
        "new_company_research_count":len(cards),
        "unique_new_domains":len(set(domains)),
        "new_research_candidates":cards,
        "verified_customer_problems_count":0,
        "authentic_buyer_replies":0,
        "confirmed_qualified_buyers":0,
        "suppression_cleared_new_contacts":0,
        "permitted_sends":0,
        "sample_requests_proven":0,
        "samples_sent":0,
        "paid_orders":0,
        "verified_revenue_usd":"0.00",
        "source_pages_officially_cryptographically_signed":False,
        "original_source_data_customer_distribution_authorized":False,
        "recommendations":[
           "Prioritize 2-3 best-fit companies for original CRM/history and suppression-owner clearance, not bulk send",
           "Check the full company and any known person-level STOP/opt-out on canonical Smart CRM, including prior threads",
           "Validate the business enquiry route is appropriate for a sales/research question before founder approves each send",
           "Begin with useful independently true DOB NOW source-check advice and one question; no price, contact scraping or invented relationship",
           "Only real direct buyer response permits next rapport step; no open/click/permit as buying signal",
           "Offer a licensed five-project mini sample only on an actual request and exact source rights/privacy clearance",
           "No recurring alerts or enterprise SLA promises until repeat source-monitoring ability and commercial terms are approved",
        ],
        "source_owner_data_field_rights_approved":False,
        "original_smart_crm_outbound_approved":False,
        "payment_activation":False,
        "no_customer_data_delivered":True,
        "outbound_sent":False,
        "smart_crm_writes":0,
        "empiredb_writes":0,
        "astra_jobs_scheduled":0,
        "execution_authority":"none",
    }
    packet["private_prospect_wave2_sha256"]=_sha(packet)
    return packet


def render_private_wave2(packet:Mapping[str,Any])->str:
    if (not isinstance(packet,Mapping) or packet.get("schema_version")!=SCHEMA
        or packet.get("mode")!="NEW_PUBLIC_PROSPECT_RESEARCH_ONLY_NO_OUTBOUND"
        or packet.get("verified_revenue_usd")!="0.00"
        or packet.get("confirmed_qualified_buyers")!=0
        or packet.get("permitted_sends")!=0
        or packet.get("outbound_sent") is not False
        or packet.get("source_owner_data_field_rights_approved") is not False
        or packet.get("original_smart_crm_outbound_approved") is not False
        or packet.get("payment_activation") is not False
        or packet.get("smart_crm_writes")!=0
        or packet.get("empiredb_writes")!=0
        or packet.get("execution_authority")!="none"
        or _sha({k:v for k,v in packet.items() if k!="private_prospect_wave2_sha256"})!=packet.get("private_prospect_wave2_sha256")):
        raise ValueError("unsafe_customer_prospect_preview")
    parts=[
        "# Empire AI / Original Permit Intelligence — NYC Prospect Wave 2",
        "",
        "**PRIVATE RESEARCH — no buyer interest, recipient approval, sending, payment or fulfilment represented.**",
        "",
        "Reviewed first-party public service pages on 24 Oct 2026; no publisher signatures; all public addresses require recheck and original CRM opt-out review.",
        "",
        "| Company | Fit / 6 (not intent) | Published work | Research contact |",
        "|---|---:|---|---|",
    ]
    for x in packet["new_research_candidates"]:
        parts.append("| "+x["company"]+" | "+str(x["objective_research_fit_points_not_buying_probability"])+
                     " | "+x["evidence_detail"]+" | "+(x["generic_inbox"] or "Unverified / form only")+" |")
    parts+=["","## Why they're relevant and the first value-first question"]
    for c in packet["new_research_candidates"]:
        parts.extend([
            "",
            "### "+c["company"],
            "- First-party scope: "+c["evidence"],
            "- Published route: "+c["contact"],
            "- Genuine source-use insight: "+c["value_insight"],
            "- Internal research-fit: "+str(c["objective_research_fit_points_not_buying_probability"])+"/6, **not** a buying probability",
            "- Buyer interest, CRM suppression, sender authority: ALL UNVERIFIED / HELD",
            "- UNSENT value-first email:",
            "",
            "> "+c["value_first_body_unsent"].replace("\n","\n> ").rstrip(" >"),
        ])
    parts.extend(["","## Release gates"])
    parts.extend("- "+r for r in packet["recommendations"])
    parts.extend(["","**No recipient cleared, no emails or samples sent, no sale or invoice, no live EmpireDB/CRM changes.**"])
    return "\n".join(parts)+"\n"
