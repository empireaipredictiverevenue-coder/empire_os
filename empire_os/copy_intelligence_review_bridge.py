"""Draft-only review boundary around the canonical EmpireOS copywriter.

This is an integration layer, not an outbound sender or proof of independent
source verification. Human review and sender authorisation remain separate.
"""
from __future__ import annotations

from datetime import date
from empire_os.copy_fingerprint import fingerprint_final_email
from typing import Any, Mapping

from empire_os.copywriter import CopyBrief, build_copy


def draft_first_touch(*, company: str, metro: str, contact_role: str,
                      product_code: str, product_name: str, audience: str,
                      trigger: Mapping[str, Any], approved_offer: Mapping[str, Any],
                      sender_email: str | None = None, brand_domain: str | None = None) -> dict[str, Any]:
    """Build a canonical draft from already-verified upstream assertions.

    Do not infer that upstream_verified actually authenticates a source; the
    supplying owner must independently validate provenance and rights.
    """
    def checked(value: Mapping[str, Any], required_kind: str) -> dict[str, str] | None:
        if not isinstance(value, Mapping) or value.get("kind") != required_kind or value.get("upstream_verified") is not True:
            return None
        statement = str(value.get("statement") or "").strip()
        source_ref = str(value.get("source_ref") or "").strip()
        observed = str(value.get("observed_date") or "")
        try:
            source_date = date.fromisoformat(observed)
        except ValueError:
            return None
        if not statement or not source_ref or source_date > date.today():
            return None
        if any(term in statement.lower() for term in ("guaranteed", "risk-free", "limited spots", "act now")):
            return None
        return {"statement": statement, "source_ref": source_ref, "observed_date": observed}

    observation = checked(trigger, "observed")
    offer = checked(approved_offer, "offer")
    if not observation or not offer:
        return {"status": "blocked_evidence", "send_allowed": False}
    if not all(str(item or "").strip() for item in (company, metro, contact_role, product_code, product_name, audience)):
        return {"status": "blocked_missing_fields", "send_allowed": False}
    try:
        brief = CopyBrief(channel="cold_email", objective="review_relevant_market_opportunity",
                          product_code=product_code, product_name=product_name,
                          audience=audience, business_name=company, metro=metro,
                          contact_title=contact_role, sender_email=sender_email,
                          brand_domain=brand_domain,
                          evidence={"why_now": {"summary": observation["statement"],
                                                   "evidence_ref": observation["source_ref"]},
                                    "offer_source_ref": offer["source_ref"]})
        draft = build_copy(brief).as_dict()
    except (ValueError, TypeError, AttributeError):
        return {"status": "blocked_canonical_validation", "send_allowed": False}
    if not isinstance(draft, dict) or not draft.get("body"):
        return {"status": "blocked_invalid_draft", "send_allowed": False}
    draft["requires_human_review"] = True
    # Content identity is not a provider delivery receipt or an approval token.
    draft_id = fingerprint_final_email(subject=draft["subject"], body=draft["body"])
    return {"status": "canonical_draft_requires_review", "draft_id": draft_id, "draft": draft,
            "source_references": {"trigger": observation["source_ref"], "offer": offer["source_ref"]},
            "source_authenticity_checked_here": False, "suppression_checked": False,
            "recipient_permission_checked": False, "founder_approved": False,
            "delivery_authority": "NONE", "send_allowed": False}
