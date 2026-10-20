"""Bounded, consent-led AI receptionist appointment/callback intake.

Only structured business metadata is kept. Never stores raw ASR transcripts,
caller numbers, names or audio. The draft is prepared for a tenant-owned CRM
review queue but does not create a canonical prospect or authorise outreach.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any

from empire_os.inbound_revenue_recovery import TenantReceptionProfile

MAX_INTAKE_ATTEMPTS = 3
TIME_WINDOWS = {
    "morning": "morning", "afternoon": "afternoon",
    "evening": "evening", "anytime": "anytime",
}


@dataclass(frozen=True)
class CRMEnquiryDraft:
    """Minimum no-PII contract for a later separately authorised CRM owner."""
    tenant_id: str
    call_id: str
    enquiry_id: str
    enquiry_type: str
    requested_service: str
    preferred_time_window: str
    caller_consented_to_review: bool
    source: str = "signed_inbound_reception_candidate"
    status: str = "PENDING_HUMAN_REVIEW_NOT_SUBMITTED"
    crm_write_performed: bool = False
    outbound_authorized: bool = False
    appointment_confirmed: bool = False
    contact_identity_included: bool = False


def speech_text(body: dict[str, Any]) -> str | None:
    """Read a bounded ASR candidate without ever persisting its raw text."""
    speech = body.get("speech")
    if not isinstance(speech, dict) or speech.get("error"):
        return None
    results = speech.get("results")
    if not isinstance(results, list) or not 1 <= len(results) <= 10:
        return None
    first = results[0]
    if not isinstance(first, dict) or not isinstance(first.get("text"), str):
        return None
    raw = first["text"].strip()
    try:
        confidence = float(first.get("confidence", 0))
    except (TypeError, ValueError, OverflowError):
        return None
    if not (0.5 <= confidence <= 1 and 0 < len(raw) <= 180):
        return None
    return raw


def normalized_speech(body: dict[str, Any]) -> str:
    text = speech_text(body) or ""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def requested_service(body: dict[str, Any], profile: TenantReceptionProfile) -> str | None:
    """Match only customer-approved, exact service phrases (no model guesses)."""
    text = normalized_speech(body)
    if not text:
        return None
    if text in {"general", "general enquiry", "general inquiry", "not sure"}:
        return "general_enquiry"
    for service in profile.services:
        if not isinstance(service, str) or not 1 <= len(service) <= 80:
            continue
        tokens = " ".join(re.findall(r"[a-z0-9]+", service.lower()))
        if tokens and re.search(r"\b" + re.escape(tokens) + r"\b", text):
            return tokens.replace(" ", "_")
    return None


def preferred_window(body: dict[str, Any]) -> str | None:
    dtmf = body.get("dtmf")
    if isinstance(dtmf, dict):
        digits = dtmf.get("digits")
        if digits in ("1", "2", "3", "4"):
            return {"1": "morning", "2": "afternoon",
                    "3": "evening", "4": "anytime"}[digits]
    text = normalized_speech(body)
    if not text:
        return None
    matches = set()
    for word, label in TIME_WINDOWS.items():
        if re.search(r"\b" + word + r"\b", text):
            matches.add(label)
    if "any time" in text or "whenever" in text or "no preference" in text:
        matches.add("anytime")
    return next(iter(matches)) if len(matches) == 1 else None


def consent_answer(body: dict[str, Any]) -> bool | None:
    """A simple yes is accepted only following the explicit contact question."""
    dtmf = body.get("dtmf")
    if isinstance(dtmf, dict):
        if dtmf.get("digits") == "1":
            return True
        if dtmf.get("digits") == "2":
            return False
    value = normalized_speech(body)
    if value in {"yes", "yes please", "yes you may contact me",
                 "i agree", "you can contact me", "i consent"}:
        return True
    if value in {"no", "no thanks", "no thank you", "do not contact me",
                 "i do not consent"}:
        return False
    return None


def draft_for_call(
    *, tenant_id: str, call_id: str, kind: str,
    service: str, window: str,
) -> CRMEnquiryDraft:
    if kind not in ("appointment", "callback"):
        raise ValueError("unsupported_enquiry_type")
    if not re.fullmatch(r"[a-z0-9_]{1,80}", service):
        raise ValueError("unsupported_service_code")
    if window not in TIME_WINDOWS.values():
        raise ValueError("unsupported_time_preference")
    # Stable per-call ID. No caller telephone number, transcript or raw name.
    digest = sha256((tenant_id + "|" + call_id + "|reception_v1").encode()).hexdigest()
    return CRMEnquiryDraft(
        tenant_id=tenant_id, call_id=call_id, enquiry_id=digest,
        enquiry_type=kind, requested_service=service,
        preferred_time_window=window,
        caller_consented_to_review=True,
    )
