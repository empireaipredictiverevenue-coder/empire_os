"""Final cold-first-touch and manual email review, independent of copy optimizers.

First-touch needs a fresh, referenced observation; no sales CTA until a
separately authenticated buyer reply is classified by the canonical
rapport_intent_cta reviewer. This module never sends or creates authority.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Mapping
import re
from empire_os.business_contact_identity import POSTAL_ADDRESS
from empire_os.conversation_value import _fresh_why_now, _specific_public_proof

POLICY="empire.rapport.value_first_final_boundary.v1"
PRICE=re.compile(r"(?:[$£€]\s*\d|\b(?:pricing|price|fee|per month|\/month|retainer)\b)",re.I)
OFFER=re.compile(
    r"\b(?:pilot|book a call|book a meeting|schedule|calendar|demo|checkout|"
    r"our (?:service|offer|product)|we offer|we sell|paid package|buy now|"
    r"payment link|reply [\"“']?(?:pilot|gap|map|sample)\b|"
    r"want me to|would you like|can i send|shall i|"
    r"grab a seat|claim a lane|let's discuss|lets discuss)\b",re.I,
)
LINK=re.compile(r"(?:https?://)?(?:www\.)?empire-ai\.co\.uk/(?:buy|checkout|pricing|book|demo)",re.I)
# One-way informational cold first touches have no requested action.
CTA=re.compile(r"\?|\b(?:reply|respond|contact me|call me|send me|let me know)\b",re.I)
FOOTER=re.compile(r"(?im)^if you.d rather not hear from me, reply .opt out.[^\n]*$")
SENSITIVE=re.compile(r"\b(?:guaranteed (?:revenue|leads|results)|ready to buy|budget available)\b",re.I)


def review_cold_message(*,subject:str,body:str,evidence_ref:str|None)->dict[str,Any]:
    if type(subject) is not str or not 1<=len(subject)<=160 or type(body) is not str or not 1<=len(body)<=5000:
        raise ValueError("BOUNDED_EMAIL_REQUIRED")
    content=FOOTER.sub("",body).strip()
    # The footer is required for governed B2B commercial mail but is exempt
    # from the general prohibition on cold email asks.
    blockers=[]
    if type(evidence_ref) is not str or not evidence_ref.strip() or evidence_ref not in content:
        blockers.append("VERIFIED_SOURCE_REFERENCE_REQUIRED")
    if PRICE.search(content) or OFFER.search(content) or LINK.search(content):
        blockers.append("COMMERCIAL_PITCH_REQUIRES_AUTHENTICATED_BUYER_SIGNAL")
    if CTA.search(content):
        blockers.append("COLD_CTA_REQUIRES_AUTHENTICATED_BUYER_SIGNAL")
    if SENSITIVE.search(content):
        blockers.append("UNVERIFIED_BUYING_INTENT_CLAIM")
    if "opt out" not in body.casefold():
        blockers.append("SUPPRESSION_FOOTER_MISSING")
    if not any(c.isalpha() for c in content):
        blockers.append("NO_USEFUL_VALUE")
    return {
        "policy":POLICY,
        "stage":"PRE_BUYER_SIGNAL",
        "approved_for_cold_content_review":not blockers,
        "blockers":sorted(set(blockers)),
        "authenticated_buyer_signal":False,
        "commercial_cta_allowed":False,
        "price_allowed":False,
        "send_authority":"none",
    }


def compose_verified_value_first(*,first_name:str,business:str,niche:str,metro:str,
                                 evidence:Mapping[str,Any],now:datetime,
                                 subject:str)->tuple[str,dict[str,Any]]:
    """Call AFTER adaptive selection and BEFORE fingerprint or outbound proposal."""
    if now.tzinfo is None:
        raise ValueError("AWARE_OBSERVATION_TIME_REQUIRED")
    trigger=_fresh_why_now(evidence,now=now)
    if not trigger:
        raise ValueError("FRESH_SOURCE_BACKED_VALUE_REQUIRED")
    # A mere prospect score, rating, synthetic trigger or generic claim
    # cannot manufacture a verified commercial problem or a buying intent.
    nested=evidence.get("why_now")
    provenance=(nested.get("observed_inferred") if isinstance(nested,Mapping)
                else evidence.get("why_now_observed_inferred"))
    if provenance in ("inferred","synthetic","fabricated") or trigger.get("observed_inferred") in ("inferred","synthetic","fabricated"):
        raise ValueError("OBSERVED_NOT_INFERRED_SOURCE_REQUIRED")
    ref=trigger["evidence_ref"]
    summary=trigger["summary"].rstrip(".")
    if any(pattern.search(summary) for pattern in (PRICE,OFFER,LINK,CTA,SENSITIVE)):
        raise ValueError("SOURCE_SUMMARY_CONTAINS_COMMERCIAL_ASK")
    proof=_specific_public_proof(evidence)
    info=(f"Public profile context: {proof}.\n" if proof else "")
    message=(
        f"Hi {first_name},\n\n"
        f"A public-source observation relevant to {business}: {summary}.\n"
        f"Source reference: {ref}.\n"
        f"{info}\n"
        f"For {niche} activity around {metro}, this is worth noting as a "
        "documented market observation, not a claim about your current plans "
        "or buying needs.\n\n"
        "Best,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        f"{POSTAL_ADDRESS}\n"
        'If you’d rather not hear from me, reply “opt out”.'
    )
    review=review_cold_message(subject=subject,body=message,evidence_ref=ref)
    if not review["approved_for_cold_content_review"]:
        raise ValueError("FIRST_TOUCH_COMMERCIAL_GATE_BLOCKED:"+",".join(review["blockers"]))
    return message,review


def review_manual_email_draft(*,subject:str,body:str,
                              evidence_ref:str|None=None,
                              verified_inbound_review:Mapping[str,Any]|None=None)->dict[str,Any]:
    """Manual Gmail/Outlook preview only; NEVER authorises external sending.

    Even an externally passed 'review_eligible' flag is not a trusted auth
    receipt in this reader. Commercial email needs a live authenticated
    same-thread reply and original canonical human approval elsewhere.
    """
    reviewed=review_cold_message(subject=subject,body=body,evidence_ref=evidence_ref)
    if verified_inbound_review is not None:
        return {
            **reviewed,
            "stage":"CLAIMED_REPLY_REQUIRES_CANONICAL_VERIFICATION",
            "approved_for_cold_content_review":False,
            "blockers":["DIRECT_EMAIL_REPLY_AUTHORITY_NOT_ESTABLISHED_BY_PAYLOAD"],
            "authenticated_buyer_signal":False,
            "commercial_cta_allowed":False,
        }
    return reviewed
