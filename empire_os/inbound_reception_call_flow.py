"""Single-worker inbound AI receptionist conversation controller (pilot candidate).

Converts signed Vonage POST answer/speech webhooks to NCCOs. Does not
register a public route, connect transfer legs, book appointments, record
audio, send SMS, run LLM inference or promise human callbacks. In-memory
sessions are ONLY for loopback dark-stage evaluation; deployment requires
durable shared replay/session storage and operator-authorised DID ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import re
from typing import Any
from urllib.parse import urlparse

from empire_os.inbound_provider_contract import InboundNumberRegistry, InboundNumberRoute
from empire_os.inbound_reception_intake import (
    CRMEnquiryDraft, MAX_INTAKE_ATTEMPTS, consent_answer, draft_for_call,
    preferred_window, requested_service,
)
from empire_os.inbound_revenue_recovery import (
    TenantReceptionProfile, plan_reception_response,
)

MAX_TURNS = 3


def normalize_did(value: str) -> str:
    """Vonage usually sends E.164 digits without leading +."""
    if not isinstance(value, str):
        raise ValueError("inbound_did_required")
    raw = value.strip()
    if raw.startswith("+"):
        raw = raw[1:]
    if not re.fullmatch(r"[1-9][0-9]{6,14}", raw):
        raise ValueError("invalid_inbound_did")
    return "+" + raw


def intent_from_speech(text: str) -> str:
    """Safe bounded intent classification; never infer commercial intent."""
    if not isinstance(text, str) or len(text) > 500:
        return "unknown"
    s = " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "
    if any(x in s for x in (" stop ", " opt out ", " do not call ", " delete my data ", " privacy ")):
        return "opt_out"
    if any(x in s for x in (" emergency ", " immediate danger ", " call an ambulance ", " fire emergency ")):
        return "emergency"
    if any(x in s for x in (" complaint ", " speak to a person ", " speak to someone ", " human ", " representative ", " operator ")):
        return "human"
    if any(x in s for x in (" appointment ", " booking ", " schedule ", " book a ", " reserve a ")):
        return "book"
    if any(x in s for x in (" call me ", " call back ", " callback ", " return my call ")):
        return "callback"
    return "unknown"


def extract_input(body: dict[str, Any]) -> str:
    """Never download optional provider audio, store raw voice, or trust ASR as fact."""
    dtmf = body.get("dtmf")
    if isinstance(dtmf, dict) and dtmf.get("digits") in ("0", "1", "2", "9"):
        return {"0": "human", "1": "book", "2": "callback", "9": "opt_out"}[dtmf["digits"]]
    speech = body.get("speech")
    if not isinstance(speech, dict) or speech.get("error"):
        return "unknown"
    results = speech.get("results")
    if not isinstance(results, list) or not results or len(results) > 10:
        return "unknown"
    best = results[0]
    if not isinstance(best, dict):
        return "unknown"
    try:
        confidence = float(best.get("confidence", 0))
    except (ValueError, TypeError, OverflowError):
        return "unknown"
    if not 0.5 <= confidence <= 1:
        return "unknown"
    text = best.get("text")
    return intent_from_speech(text)


def build_ncco(text: str, event_url: str | None, *, lang: str = "en-GB") -> list[dict[str, Any]]:
    """Vonage NCCO talk/input; avoid automatic recording and chargeable transfer."""
    if not isinstance(text, str) or not 0 < len(text) <= 850:
        raise ValueError("invalid_reception_speech")
    if lang not in ("en-GB", "en-US"):
        raise ValueError("unsupported_reception_voice_language")
    ncco: list[dict[str, Any]] = [{
        "action": "talk", "text": text, "language": lang,
        "bargeIn": False,
    }]
    if event_url is not None:
        parsed = urlparse(event_url)
        if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment
            or parsed.query or not parsed.path.startswith("/v1/inbound-reception/")):
            raise ValueError("inbound_input_requires_explicit_https_event")
        ncco.append({
            "action": "input", "type": ["speech", "dtmf"],
            "dtmf": {"maxDigits": 1, "timeOut": 5},
            "speech": {
                "endOnSilence": 1.5, "startTimeout": 8,
                "maxDuration": 15, "saveAudio": False,
            },
            "eventUrl": [event_url], "eventMethod": "POST",
        })
    return ncco


@dataclass
class CallSession:
    call_uuid: str
    tenant_id: str
    did: str
    turns: int = 0
    closed: bool = False
    last_action: str = "greeted"
    intake_stage: str = ""
    enquiry_kind: str = ""
    requested_service: str = ""
    preferred_time_window: str = ""
    intake_attempts: int = 0


class InboundReceptionCallEngine:
    """Provider DID, never caller-provided tenant, determines the customer."""

    def __init__(
        self,
        routes: tuple[InboundNumberRoute, ...],
        profiles: dict[str, TenantReceptionProfile],
        *,
        event_url: str,
        max_sessions: int = 500,
        on_consented_draft: Callable[[CRMEnquiryDraft], bool] | None = None,
    ):
        self.registry = InboundNumberRegistry(routes)
        self.profiles = dict(profiles)
        if not (1 <= max_sessions <= 5000):
            raise ValueError("invalid_session_cap")
        self.max_sessions = max_sessions
        if on_consented_draft is not None and not callable(on_consented_draft):
            raise ValueError("valid_reception_draft_sink_required")
        self.on_consented_draft = on_consented_draft
        self.sessions: dict[str, CallSession] = {}
        self.pending_handoffs: dict[tuple[str, str], CRMEnquiryDraft] = {}
        self.event_url = event_url
        # Validate the fixed callback URL now instead of at call answer time.
        build_ncco("Configuration check", event_url)

    def _resolve_route(self, body: dict[str, Any]) -> tuple[InboundNumberRoute, TenantReceptionProfile]:
        route = self.registry.resolve(normalize_did(body.get("to")))
        profile = self.profiles.get(route.tenant_id)
        if (profile is None or profile.tenant_id != route.tenant_id
            or profile.business_name != route.business_name):
            raise ValueError("inbound_route_profile_authority_mismatch")
        supplied_tenant = body.get("tenant_id")
        if supplied_tenant is not None and supplied_tenant != route.tenant_id:
            raise ValueError("external_tenant_claim_not_authorized")
        return route, profile

    @staticmethod
    def _call_id(body: dict[str, Any]) -> str:
        uuid = body.get("uuid")
        if not isinstance(uuid, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,96}", uuid):
            raise ValueError("provider_call_uuid_invalid")
        return uuid

    def answer(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        route, profile = self._resolve_route(body)
        uuid = self._call_id(body)
        session = self.sessions.get(uuid)
        if session:
            if session.tenant_id != route.tenant_id or session.did != route.e164_number:
                raise ValueError("call_uuid_reused_across_tenants")
        else:
            if len(self.sessions) >= self.max_sessions:
                raise ValueError("reception_session_capacity_held")
            self.sessions[uuid] = CallSession(uuid, route.tenant_id, route.e164_number)
        if session and session.closed:
            return build_ncco("This reception session has ended. Thank you for calling.", None)
        if session and session.turns > 0:
            raise ValueError("answer_replayed_after_reception_turn")
        return build_ncco(
            f"Hello, you've reached {profile.business_name}'s AI receptionist. "
            "I can help you ask about an appointment or a callback. "
            "For a person, press zero. For an appointment, press one. "
            "For a callback, press two. How can I help?",
            self.event_url,
            lang="en-GB" if profile.locale == "en-GB" else "en-US",
        )

    def reply(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        route, profile = self._resolve_route(body)
        uuid = self._call_id(body)
        session = self.sessions.get(uuid)
        if session is None or session.tenant_id != route.tenant_id or session.did != route.e164_number:
            raise ValueError("unknown_or_cross_tenant_call_session")
        if session.closed:
            return build_ncco("Thank you. This conversation has ended.", None)
        session.turns += 1
        intent = extract_input(body)
        # A privacy stop, emergency, or request for a person interrupts even
        # a partially completed appointment/callback questionnaire.
        if session.intake_stage and intent in {"opt_out", "emergency", "human"}:
            session.closed = True
            session.last_action = intent
            session.intake_stage = ""
            session.requested_service = ""
            session.preferred_time_window = ""
            decision = plan_reception_response(profile, intent)
            return build_ncco(decision.spoken_text, None)
        if session.intake_stage:
            return self._reply_intake(session, profile, body)
        if intent in {"book", "callback"}:
            session.enquiry_kind = "appointment" if intent == "book" else "callback"
            session.intake_stage = "service"
            session.intake_attempts = 0
            offerings = [
                value for value in profile.services
                if isinstance(value, str)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9 -]{0,59}", value)
            ]
            services = ", ".join(offerings[:3]) or "general enquiry"
            session.last_action = "enquiry_service_requested"
            return build_ncco(
                "I can prepare your " + session.enquiry_kind
                + " request, but cannot confirm a time yet. "
                + "What service do you need? You can say "
                + services + ", or general enquiry.",
                self.event_url,
            )
        if intent == "unknown":
            if session.turns >= MAX_TURNS:
                session.closed = True
                session.last_action = "human_followup_needed"
                return build_ncco(
                    "Sorry, I couldn't understand. Please contact the team directly. "
                    "I haven't booked anything or requested a callback. Goodbye.",
                    None,
                )
            session.last_action = "clarify"
            return build_ncco(
                "Sorry, I didn't catch that. Say appointment, callback, or human. "
                "Or press one, two, or zero.",
                self.event_url,
            )
        decision = plan_reception_response(profile, intent)
        session.last_action = decision.action
        # No transfer, booking, SMS or personal-data capture before an explicit
        # consented, owner-connected customer integration is verified.
        session.closed = True
        return build_ncco(
            decision.spoken_text
            + " I have not placed a booking or arranged an outgoing call. "
            "Please contact the business directly if you need immediate follow-up. Goodbye.",
            None,
        )


    def _retry_intake(self, session: CallSession, prompt: str) -> list[dict[str, Any]]:
        session.intake_attempts += 1
        if session.intake_attempts >= MAX_INTAKE_ATTEMPTS:
            session.closed = True
            session.last_action = "intake_needs_human"
            session.intake_stage = ""
            session.requested_service = ""
            session.preferred_time_window = ""
            return build_ncco(
                "Sorry, I couldn't capture that request clearly. "
                "Nothing was sent or booked. Please contact the business directly. Goodbye.",
                None,
            )
        return build_ncco(prompt, self.event_url)

    def _reply_intake(
        self,
        session: CallSession,
        profile: TenantReceptionProfile,
        body: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if session.intake_stage == "service":
            category = requested_service(body, profile)
            if category is None:
                return self._retry_intake(
                    session,
                    "Which service would you like? Please say one of the business's "
                    "listed services, or say general enquiry.",
                )
            session.requested_service = category
            session.intake_stage = "window"
            session.intake_attempts = 0
            session.last_action = "enquiry_preference_requested"
            return build_ncco(
                "Thank you. When would you prefer the team to consider your request? "
                "Say morning, afternoon, evening, or anytime. "
                "You can also press one, two, three, or four.",
                self.event_url,
            )
        if session.intake_stage == "window":
            window = preferred_window(body)
            if window is None:
                return self._retry_intake(
                    session,
                    "Please say morning, afternoon, evening or anytime. "
                    "Or press one for morning, two for afternoon, three for evening, "
                    "or four for anytime.",
                )
            session.preferred_time_window = window
            session.intake_stage = "permission"
            session.intake_attempts = 0
            session.last_action = "explicit_contact_consent_requested"
            return build_ncco(
                "May the business team contact you about this "
                + session.enquiry_kind + " enquiry? "
                "Say yes, you may contact me, or press one for yes. "
                "Say no, or press two for no. "
                "No appointment will be booked by this request.",
                self.event_url,
            )
        if session.intake_stage == "permission":
            permission = consent_answer(body)
            if permission is None:
                return self._retry_intake(
                    session,
                    "To allow this enquiry to be prepared for team review, "
                    "say yes, you may contact me, or press one. "
                    "To decline, say no or press two.",
                )
            if permission is False:
                session.closed = True
                session.intake_stage = ""
                session.last_action = "contact_permission_declined"
                session.requested_service = ""
                session.preferred_time_window = ""
                return build_ncco(
                    "Understood. I won't prepare this enquiry for follow-up. "
                    "No appointment has been booked, and no callback has been arranged. Goodbye.",
                    None,
                )
            packet = draft_for_call(
                tenant_id=session.tenant_id,
                call_id=session.call_uuid,
                kind=session.enquiry_kind,
                service=session.requested_service,
                window=session.preferred_time_window,
            )
            key = (session.tenant_id, session.call_uuid)
            if key in self.pending_handoffs and self.pending_handoffs[key] != packet:
                raise ValueError("conflicting_reception_enquiry")
            # Persist (local dark staging only) before acknowledging anything.
            # If the durable sink fails, keep the consent step retryable and
            # never emit a false receipt or enqueue a phantom CRM enquiry.
            if self.on_consented_draft is not None:
                try:
                    sink_result = self.on_consented_draft(packet)
                    if type(sink_result) is not bool:
                        raise ValueError("reception_draft_sink_receipt_not_boolean")
                except Exception as exc:
                    raise ValueError("reception_draft_sink_unavailable") from exc
            self.pending_handoffs[key] = packet
            session.closed = True
            session.intake_stage = ""
            session.last_action = "enquiry_drafted_for_human_review"
            session.requested_service = ""
            session.preferred_time_window = ""
            return build_ncco(
                "Thank you. I've prepared your enquiry for review, "
                "but it has not yet been sent to the business team. "
                "No appointment has been booked or callback arranged. Goodbye.",
                None,
            )
        raise ValueError("unknown_reception_intake_stage")

    def review_handoffs_for_tenant(self, tenant_id: str) -> tuple[CRMEnquiryDraft, ...]:
        """Private in-process CRM contract, not a customer-facing read route."""
        if tenant_id not in self.profiles:
            raise ValueError("unregistered_reception_tenant")
        return tuple(
            packet for (tenant, _), packet in self.pending_handoffs.items()
            if tenant == tenant_id
        )
