"""Original EmpireOS Permit Intelligence NYC contractor prospect research WAVE 3.

First-party company pages observed 24 Oct 2026; no buyer intent inferred.
Distinct from prior 5+8 SHA-custodied companies. Existing original CRM owner
and value-first strategy mandatory; no contact, payments, or unlicensed data.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json
from typing import Mapping,Any

from empire_os.buyer_network_contact_history_gate import review
from empire_os.permit_prospect_wave2 import SCHEMA as WAVE2_SCHEMA
from empire_os.permit_controlled_seed_receipt import SCHEMA as SEED_SCHEMA
SCHEMA="empire.permit_data.nyc_prospect_wave3_owner_hold.v1"
ROWS=(
 ("WNW & Sons Fire Sprinklers","wnwfiresprinklers.com","sprinklers@wnwsons.com",
  "https://www.wnwfiresprinklers.com/projects.html",
  "https://wnwfiresprinklers.com/contact.html","589 East 56th Street, Brooklyn, NY 11203",
  "Directly describes DOB filing, installation, job sign-off and estimates",True,True,
  "Do your estimators check whether an approved DOB NOW sprinkler application actually has an issued permit before researching it?"),
 ("Capitol Fire Sprinkler","capitolfire.com","info@capitolfire.com",
  "https://www.capitolfire.com/","https://www.capitolfire.com/contact-us",
  "51-51 59th Place, Woodside, NY 11377",
  "Separate new-installation division plus NYC FDNY compliance and inspections",True,True,
  "Does your new-installation team manually recheck sprinkler filing stages when choosing projects to investigate?"),
 ("Empire State Fire Sprinkler Corp","empirefire.net","info@empirefire.net",
  "https://www.empirefire.net/","https://www.empirefire.net/blank-2",
  "1358 Utica Avenue, Brooklyn, NY 11203",
  "Publicly advertises sprinkler installation, FDNY violations and NFPA 25 inspection",True,True,
  "Would a dated distinction between approved applications and independently issued permits improve your project research?"),
 ("Patriot Fire Suppression LLC","patriotfireny.com","info@patriotfireny.com",
  "https://patriotfireny.com/","https://patriotfireny.com/",
  "260 Madison Avenue, New York, NY 10016",
  "New sprinkler and standpipe installations with NYC fire-code project management",True,True,
  "Does the team already have a quick way to verify application changes separately from confirmed permit issuance?"),
 ("Precision Sprinkler Services","precisionsprinklerny.com","info@precisionsprinklerny.com",
  "https://www.precisionsprinklerny.com/","https://www.precisionsprinklerny.com/contact",
  "2113 Williamsbridge Road, Bronx, NY 10461",
  "Installation, FDNY and DOB violation corrections and sprinkler maintenance",True,True,
  "When researching installation work, which DOB filing stages do you find yourself checking repeatedly?"),
 ("Allstate Sprinkler Corp","allstatesprinkler.com",None,
  "https://allstatesprinkler.com/about","https://allstatesprinkler.com/locations/bronx",
  "1869 White Plains Road, Bronx, NY 10462",
  "Sprinkler installations, alterations and licensed NYC suppression contracting",True,True,
  "Would dated, source-checked sprinkler filing changes reduce manual crosschecking for your team?"),
 ("Metro Fire Inspections","metrofireinspections.com","general@metrofireinspections.com",
  "https://metrofireinspections.com/","https://metrofireinspections.com/",
  "150 Jerusalem Avenue, Massapequa, NY 11758",
  "Design/installation and NYC-project portfolio alongside inspection and service",True,False,
  "Does your team monitor filing changes for NYC installation and upgrade opportunities alongside recurring inspections?"),
 ("RAEL Fire Protection","raelfireprotection.com","info@raelfireprotection.com",
  "https://raelfireprotection.com/","https://raelfireprotection.com/privacy-policy/",
  "1750 Plaza Avenue, New Hyde Park, NY 11040",
  "Design/installation plus existing REDi digital compliance platform",True,False,
  "Does your existing REDi workflow already cover external DOB NOW application-to-issued-permit research?"),
)
def digest(x:Mapping[str,Any])->str:
    return sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def build(*,old_first:Mapping[str,Any],old_second:Mapping[str,Any],seed:Mapping[str,Any],
          context:Mapping[str,Any],at:datetime)->dict:
    if not isinstance(at,datetime) or at.utcoffset() is None: raise ValueError("aware_prospect_clock")
    if (old_first.get("schema_version")!="empire.permit_data.private_first_customer_outreach_proposals.v1"
        or old_first.get("private_proposal_sha256")!=digest({k:v for k,v in old_first.items() if k!="private_proposal_sha256"})
        or old_first.get("outbound_eligible")!=0 or old_first.get("outbound_sent") is not False):
        raise ValueError("original_first_five_sha_not_valid")
    if (old_second.get("schema_version")!=WAVE2_SCHEMA
        or old_second.get("private_prospect_wave2_sha256")!=digest({k:v for k,v in old_second.items() if k!="private_prospect_wave2_sha256"})
        or old_second.get("new_company_research_count")!=8 or old_second.get("outbound_sent") is not False
        or old_second.get("verified_revenue_usd")!="0.00"):
        raise ValueError("original_second_eight_sha_not_valid")
    if (seed.get("schema_version")!=SEED_SCHEMA
        or seed.get("controlled_seed_sha256")!=digest({k:v for k,v in seed.items() if k!="controlled_seed_sha256"})
        or seed.get("controlled_gmail_inbox_observed") is not True
        or seed.get("emails_sent_to_actual_prospects")!=0
        or seed.get("permit_outreach_approved") is not False
        or seed.get("real_prospect_inbox_placement_rate") is not None):
        raise ValueError("original_controlled_sender_evidence_invalid")
    if (not isinstance(context,Mapping) or type(context.get("available")) is not bool
        or type(context.get("gmail_snapshot_fresh")) is not bool
        or not isinstance(context.get("relationships"),Mapping)
        or not isinstance(context.get("observations"),Mapping)):
        raise ValueError("untrusted_original_live_crm_context")
    existing={r["domain"] for r in old_first["drafts"]}|{r["domain"] for r in old_second["new_research_candidates"]}
    if len(existing)!=13 or len({r[1] for r in ROWS})!=8 or existing.intersection({r[1] for r in ROWS}):
        raise ValueError("duplicate_or_missing_original_cohort")
    candidates=[]
    for name,domain,address,source,contact,location,services,install,dob,question in ROWS:
        if (not source.startswith("https://") or not contact.startswith("https://")
            or question.count("?")!=1 or "$" in question):
            raise ValueError("untrusted_first_party_research_record")
        status=review(domain,context)
        if (status.get("outbound_authorized") is not False
            or not isinstance(status.get("state"),str)):
            raise ValueError("untrusted_original_contact_state")
        # Transparent service-fit score, never probabilities.
        fit=2+2*int(install)+int(dob)+int(bool(address))
        first=(
            f"Hello {name} team,\n\n"
            "A useful NYC DOB NOW check: an approved application does not by "
            "itself confirm a permit has been issued, much less an available "
            "contract. Checking the exact filing and date can prevent wasted "
            "estimating research.\n\n"
            f"I noticed your published services include {services.lower()}. "
            f"{question}\n\n"
            "An email reply is fine—no call necessary. "
            "Please say if you would prefer no further contact.\n\n"
            "Empire AI | Permit Intelligence\n"
        )
        if first.count("?")!=1 or "$" in first or "@" in first:
            raise ValueError("value_first_message_not_unpriced_or_bounded")
        holds=["PERSON_LEVEL_SUPPRESSION_NOT_CLEARED","NO_FOUNDER_EXACT_COPY_SEND_APPROVAL",
               "NO_CONFIRMED_BUYER_NEED","PROSPECT_INBOX_PLACEMENT_UNKNOWN",
               "CUSTOMER_FIELD_RIGHTS_HELD"]
        if not status["history_verified_complete"] or not status["gmail_snapshot_fresh"]:
            holds.append("CANONICAL_GMAIL_HISTORY_STALE_OR_INCOMPLETE")
        if status["state"] in ("DO_NOT_PURSUE","DELIVERY_HOLD") or status["confirmed_hard_bounce"]:
            holds.append("STOP_OR_BOUNCE_NO_CONTACT")
        if status["state"] in ("ALREADY_CONTACTED","EXISTING_CONVERSATION","FOUNDER_FORM_SUBMITTED"):
            holds.append("PRIOR_CONTACT_REVIEW_INSTEAD_OF_NEW_OUTREACH")
        if address is None:
            holds.append("NO_FIRST_PARTY_PUBLIC_GENERAL_EMAIL_ROUTE")
        candidates.append({
          "company":name,"domain":domain,"generic_public_business_email":address,
          "official_service_source":source,"official_contact_source":contact,
          "official_business_address":location,"published_services":services,
          "source_review_day":"2026-10-24","new_installation_work":install,
          "explicit_dob_or_fdny_relevance":dob,
          "service_fit_points_not_buyer_propensity":fit,"maximum_service_fit_points":6,
          "contact_domain_differs_from_company_website":address is not None and address.split("@")[1]!=domain,
          "possible_existing_competing_intelligence_stack":domain=="raelfireprotection.com",
          "canonical_contact_history_state":status["state"],
          "canonical_history_complete":status["history_verified_complete"],
          "canonical_gmail_snapshot_fresh":status["gmail_snapshot_fresh"],
          "verified_buyer_interest":False,"person_level_optout_cleared":False,
          "recipient_email_reachability_verified":False,
          "actual_inbox_placement_verified":False,"individual_recipient_approved":False,
          "send_allowed":False,"email_sent":False,
          "sample_requested":False,"external_sample_sent":False,
          "subject_unsent":"NYC DOB NOW filing research — one useful check",
          "value_first_message_unsent":first,
          "one_workflow_question":question,
          "blockers":sorted(set(holds)),
          "research_fit_not_sales_intent":True,
        })
    candidates.sort(key=lambda x:(-x["service_fit_points_not_buyer_propensity"],
                                  x["company"].lower()))
    output={
      "schema_version":SCHEMA,"mode":"PRIVATE_REAL_FIRST_PARTY_PROSPECT_RESEARCH_NO_SEND",
      "researched_at_utc":at.astimezone(timezone.utc).isoformat(),
      "original_first_wave_sha256":old_first["private_proposal_sha256"],
      "original_second_wave_sha256":old_second["private_prospect_wave2_sha256"],
      "original_real_gmail_seed_sha256":seed["controlled_seed_sha256"],
      "previous_distinct_company_count":13,"new_distinct_company_count":8,
      "combined_unique_company_research_count":21,
      "new_prospect_research":candidates,
      "first_party_public_generic_email_routes":sum(x["generic_public_business_email"] is not None for x in candidates),
      "original_canonical_history_available":context["available"],
      "original_gmail_snapshot_fresh":context["gmail_snapshot_fresh"],
      "source_pub_claims_not_verified_third_party_certifications":True,
      "email_open_click_or_permit_is_not_a_buyer_signal":True,
      "original_value_rapport_signal_cta_sequence_locked":True,
      "actual_buyers":0,"original_suppression_cleared_recipients":0,
      "genuine_buyer_replies":0,"prospect_emails_sent":0,
      "first_contact_sample_attached":False,
      "outlook_inbox_reachability_measured":False,
      "actual_recipient_inbox_rate":None,
      "verified_revenue_usd":"0.00",
      "source_owner_customer_distribution_approved":False,
      "founder_send_approved":False,"outbound_sent":False,
      "empiredb_writes":0,"smart_crm_writes":0,"astra_jobs":0,
      "checkout_activated":False,"execution_authority":"none",
      "owner_next_action":"Refresh canonical contact history; verify individual suppression, appropriate business route, permitted source field use and exact founder copy before any genuine value-first send."
    }
    output["private_prospect_wave3_sha256"]=digest(output)
    return output

def render(report:Mapping[str,Any])->str:
    if (report.get("schema_version")!=SCHEMA
        or report.get("private_prospect_wave3_sha256")!=digest({k:v for k,v in report.items() if k!="private_prospect_wave3_sha256"})
        or report.get("prospect_emails_sent")!=0 or report.get("verified_revenue_usd")!="0.00"
        or report.get("outbound_sent") is not False
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_wave3_report")
    lines=["# Empire AI Permit Intelligence — NYC Prospect Wave 3","",
        "**Founder-private research; no sends, no bought leads, no paying clients claimed.**","",
        "| Company | Service-fit /6, NOT buyer propensity | Original CRM history | First-party general inbox |",
        "|---|---:|---|---|"]
    for c in report["new_prospect_research"]:
        lines.append(f"| {c['company']} | {c['service_fit_points_not_buyer_propensity']} | {c['canonical_contact_history_state']} | {c['generic_public_business_email'] or 'NOT FIRST-PARTY VERIFIED'} |")
    for c in report["new_prospect_research"]:
        lines += ["",f"## {c['company']}",
          "- First-party service evidence: "+c["official_service_source"],
          "- First-party contact evidence: "+c["official_contact_source"],
          "- Published service: "+c["published_services"],
          "- Contact history: "+c["canonical_contact_history_state"]+" (no send clearance)",
          "- Value-first UNSENT message:","",c["value_first_message_unsent"],
          "- Held: "+", ".join(c["blockers"])]
    lines+=["","**Previous 13 remain intact. 8 new = 21 distinct researched companies.**",
      "One controlled Gmail seed was received, not a contractor Inbox measurement.",
      "Outlook not measured; recipient suppression, sample sharing and sales activation HELD.",
      "No first-party address alone proves actual mailbox acceptance or lawful outreach.",
      "**0 outbound; 0 genuine buyer replies; $0 verified revenue; 0 production changes.**"]
    return "\n".join(lines)+"\n"
