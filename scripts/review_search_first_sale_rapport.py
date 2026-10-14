"""Three-prospect relationship-first review, using existing Outbound Department.

Read-only research adapter. No DB, network, mail, CRM mutations or timers.
Never passes founder/suppression/provider send authority to a campaign.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from empire_os.outbound_department import plan_outbound_account, review_outbound_draft

# Candidate research only; 'pending' means this packet awaits founder review,
# NOT an approved EmpireDB customer or send permission.
PROSPECTS=(
    {
        "key":"green_coast",
        "company_name":"Green Coast Roofing & Solar",
        "person":"Brian Sujevich",
        "email":"brian@gogreencoast.com",
        "contact_route":"person_bound",
        "source_ref":"public:green-coast-2026-10-04-relaunch",
        "source_url":"https://www.prweb.com/releases/green-coast-roofing-and-solar-marks-more-than-five-decades-of-family-owned-roofing-in-southwest-florida-302897553.html",
        "observation":"Green Coast Roofing & Solar recently announced its redesigned website.",
        "fresh":True,
        "subject":"Green Coast's website launch",
        "body":(
            "Hi Brian,\n\nI saw Green Coast Roofing & Solar announced its redesigned "
            "website this month. Bringing roofing and solar into one clear "
            "experience for customers looks like a substantial project. "
            "Thought it was worth recognising the work behind the launch.\n\n"
            "Best,\nPhil\nFounder, Empire AI"
        ),
        "recipient_identity_currently_verified":False,
    },
    {
        "key":"roofelite",
        "company_name":"RoofElite",
        "person":"Trey Gifford",
        "email":None,
        "contact_route":None,
        "source_ref":"public:roofelite-2026-04-facility",
        "source_url":"https://www.globenewswire.com/news-release/2026/04/28/3283294/0/en/RoofElite-Expands-Tampa-Operations-With-New-6-000-sq-Ft-Facility-Strengthening-In-House-Capabilities-and-Capacity.html",
        "observation":"RoofElite announced expanded Tampa operations and a larger facility in April.",
        "fresh":False,  # April event alone is not a current fresh sales signal.
        "subject":"RoofElite's Tampa expansion",
        "body":(
            "Hi Trey,\n\nI saw RoofElite's update about expanding Tampa operations "
            "and bringing more work in-house. Supporting a growing team across "
            "commercial and residential roofing is quite a shift. "
            "Thought the expansion was worth acknowledging.\n\n"
            "Best,\nPhil\nFounder, Empire AI"
        ),
        "recipient_identity_currently_verified":False,
    },
    {
        "key":"aastro",
        "company_name":"Aastro Roofing",
        "person":"Jason Blair",
        "email":None,
        "contact_route":None,
        "source_ref":"public:aastro-2026-09-16-expansion",
        "source_url":"https://www.prnewswire.com/news-releases/aastro-roofing-expands-into-full-service-general-contracting-offering-more-than-just-roofing-302880457.html",
        "observation":"Aastro Roofing recently announced expansion into general contracting.",
        "fresh":True,
        "subject":"Aastro's wider service mix",
        "body":(
            "Hi Jason,\n\nI saw Aastro Roofing's announcement about adding "
            "general contracting alongside roofing. New types of projects "
            "bring different decisions for homeowners and property teams. "
            "It was interesting to see you broadening the work you take on.\n\n"
            "Best,\nPhil\nFounder, Empire AI"
        ),
        "recipient_identity_currently_verified":False,
    },
)


def review_candidate(
    candidate: Mapping[str,Any], *,
    history=(), replies=(), suppressions=(), evidence=None,
    model_decision=None, canonical_suppression_cleared=False,
)->dict[str,Any]:
    """Only current, independent external governance can authorise a send."""
    account={
        "company_name":candidate["company_name"],
        "company_name_verified":True,
        "decision_maker":candidate["person"],
        "contact_email":candidate.get("email"),
        "contact_route":candidate.get("contact_route"),
        "person_bound":candidate.get("contact_route")=="person_bound",
        "buyer_review_status":"pending",
        "product_code":(
            "technical_search_audit"
            if candidate["key"] in ("green_coast","roofelite")
            else "search_opportunity_map"
        ),
        "verified_reply_required_for_followup":True,
        # Only a canonical reader can supply these later: no IDs invented
        # for research-only prospects.
        "tenant_id":candidate.get("tenant_id"),
        "prospect_id":candidate.get("prospect_id"),
        "original_outbound_intent_id":candidate.get("original_outbound_intent_id"),
    }
    observations=list(evidence) if evidence is not None else [{
        "evidence_ref":candidate["source_ref"],
        "summary":candidate["observation"],
        "verified":True,  # verified fact, not proof of buyer demand
        "fresh":candidate["fresh"],
        "account_bound":True,
    }]
    plan=plan_outbound_account(
        account, history=history, evidence=observations,
        replies=replies, suppressions=suppressions,
        intent_decision=model_decision,
        canonical_suppression_cleared=canonical_suppression_cleared,
    )
    copy=None
    if plan["action_type"]=="DRAFT_RAPPORT_TOUCH":
        copy=review_outbound_draft(
            account=account,plan=plan,
            subject=candidate["subject"],body=candidate["body"],
            used_evidence_refs=[candidate["source_ref"]],
        )
    return {
        "schema_version":"empire.search.first_sale.rapport_review.v1",
        "prospect_key":candidate["key"],
        "company_name":candidate["company_name"],
        "relationship_stage":plan["relationship_stage"],
        "next_action":plan["action_type"],
        "rapport_policy":"rapport_first_human_specific_v1",
        "strict_verified_reply_required":True,
        "intent_cta_review":plan.get("intent_cta_review"),
        "subject":candidate["subject"],
        "first_touch_body":candidate["body"],
        "copy_review":copy,
        "source_ref":candidate["source_ref"],
        "source_url":candidate["source_url"],
        "current_recipient_identity_cleared":False,
        "canonical_suppression_cleared":False,
        "professional_mailbox_send_authorized":False,
        "founder_send_approved":False,
        "automatic_followup":False,
        "product_pitch_in_first_touch":False,
        "execution_authority":"none",
        "outbound_sent":False,
        "send_authorized":False,
    }


def main() -> int:
    reviews=[review_candidate(item) for item in PROSPECTS]
    print(json.dumps({
        "mode":"FOUNDER_REVIEW_ONLY",
        "reviews":reviews,
        "outbound_sent":False,
        "orders_created":0,
        "database_writes":False,
    },indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
