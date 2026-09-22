"""Governed call-manager planning for EmpireOS.

Builds ranked, context-rich voice call work from the durable call-ready queue.
It never places a call, opens a provider session, sends SMS, accepts terms,
moves funds, or declares revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping
import urllib.parse

from empire_os.buyer_deferred_enrichment import CALL_READY_PATH
from empire_os.qualification_worker_v2 import request_json
from empire_os.vonage_call_transport import VonageCallConfig, VonageCallTransport


Request = Callable[..., Any]


@dataclass(frozen=True)
class CallWorkItem:
    prospect_id: str
    business_name: str
    phone: str
    niche: str
    metro: str
    website: str
    buy_signal_score: float | None
    qualification_tier: str | None
    qualification_score: float | None
    reason: str
    enrichment_attempts: int
    priority_score: float
    priority_reasons: tuple[str, ...]
    closer_brief: Mapping[str, Any]
    voice_legal_basis: str | None
    line_type: str | None
    legal_basis_source: str | None
    channel: str = "voice"
    provider: str = "vonage"
    state: str = "ready_for_review"
    execution_allowed: bool = False
    requires_live_call_authority: bool = True

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["priority_reasons"] = list(self.priority_reasons)
        data["closer_brief"] = dict(self.closer_brief)
        return data


def _get(
    request: Request,
    path: str,
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request("GET", f"{path}?{query}") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _load_queue(path: str | Path = CALL_READY_PATH) -> dict[str, dict[str, Any]]:
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _priority(
    *,
    buy_signal_score: float | None,
    tier: str | None,
    qualification_score: float | None,
    reason: str,
    attempts: int,
) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    reasons: list[str] = []

    if buy_signal_score is not None:
        score += min(35.0, max(0.0, buy_signal_score * 0.35))
        reasons.append(f"buy_signal:{buy_signal_score:g}")

    tier_weight = {
        "hot": 35.0,
        "warm": 24.0,
        "cold": 8.0,
        "insufficient_evidence": 4.0,
    }.get(str(tier or "").strip().lower(), 0.0)
    if tier_weight:
        score += tier_weight
        reasons.append(f"qualification_tier:{tier}")

    if qualification_score is not None:
        normalized = (
            qualification_score * 20.0
            if 0.0 <= qualification_score <= 1.0
            else min(20.0, max(0.0, qualification_score * 0.20))
        )
        score += normalized
        reasons.append(f"qualification_score:{qualification_score:g}")

    if reason == "no_bound_contact":
        score += 8.0
        reasons.append("decision_contact_partially_observed")
    elif reason == "no_contact_evidence":
        score += 5.0
        reasons.append("decision_identity_without_email")
    elif reason == "no_decision_maker":
        score += 3.0
        reasons.append("phone_fallback_for_identity_recovery")
    elif reason == "site_unavailable":
        score += 1.0
        reasons.append("phone_only_fallback")

    score -= min(10.0, max(0, attempts - 1) * 2.0)
    if attempts > 1:
        reasons.append(f"enrichment_attempts:{attempts}")

    return round(max(0.0, score), 2), tuple(reasons)


def build_call_work(
    request: Request = request_json,
    *,
    queue_path: str | Path = CALL_READY_PATH,
    limit: int = 25,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 100))
    queue = _load_queue(queue_path)
    items: list[CallWorkItem] = []

    for raw in queue.values():
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") != "ready_for_review":
            continue
        prospect_id = str(raw.get("prospect_id") or "").strip()
        phone = str(raw.get("phone") or "").strip()
        if not prospect_id or not phone:
            continue

        prospect_rows = _get(
            request,
            "/rest/v1/prospects",
            {
                "select": (
                    "id,business_name,niche,metro,website,phone,"
                    "buy_signal_score,status,contact_name,contact_title"
                ),
                "id": f"eq.{prospect_id}",
                "limit": 1,
            },
        )
        prospect = prospect_rows[0] if prospect_rows else {}

        q_rows = _get(
            request,
            "/rest/v1/prospect_qualifications",
            {
                "select": "tier,score,scored_at",
                "prospect_id": f"eq.{prospect_id}",
                "order": "scored_at.desc",
                "limit": 1,
            },
        )
        qualification = q_rows[0] if q_rows else {}

        buy_signal = _float(prospect.get("buy_signal_score"))
        q_score = _float(qualification.get("score"))
        tier = str(qualification.get("tier") or "").strip() or None
        reason = str(raw.get("reason") or "").strip()
        attempts = max(1, int(raw.get("enrichment_attempts") or 1))
        priority, priority_reasons = _priority(
            buy_signal_score=buy_signal,
            tier=tier,
            qualification_score=q_score,
            reason=reason,
            attempts=attempts,
        )

        business_name = str(
            prospect.get("business_name")
            or raw.get("business_name")
            or ""
        ).strip()
        niche = str(prospect.get("niche") or "").strip()
        metro = str(prospect.get("metro") or "").strip()
        website = str(
            prospect.get("website")
            or raw.get("website")
            or ""
        ).strip()

        brief = {
            "objective": (
                "Identify the decision maker and test commercial interest "
                "without inventing demand, pricing, capacity, or outcomes."
            ),
            "opening_context": {
                "business_name": business_name,
                "niche": niche,
                "metro": metro,
                "reason_for_phone_fallback": reason,
            },
            "qualification": {
                "tier": tier,
                "score": q_score,
                "buy_signal_score": buy_signal,
            },
            "required_capture": [
                "decision_maker_name",
                "decision_maker_role",
                "best_work_email_if_offered",
                "territory",
                "daily_capacity",
                "interest_signal",
                "objection_or_question",
                "permission_for_follow_up",
            ],
            "prohibited_commitments": [
                "invented lead volume",
                "unapproved pricing",
                "exclusivity commitment",
                "payment confirmation",
                "revenue declaration",
            ],
            "conversation_os": {
                "channel": "voice",
                "provider": "vonage",
                "transcript_required": True,
                "qualification_evidence_required": True,
            },
        }

        voice_legal_basis = str(
            raw.get("voice_legal_basis") or ""
        ).strip() or None
        line_type = str(raw.get("line_type") or "").strip() or None
        legal_basis_source = str(
            raw.get("legal_basis_source") or ""
        ).strip() or None

        items.append(CallWorkItem(
            prospect_id=prospect_id,
            business_name=business_name,
            phone=phone,
            niche=niche,
            metro=metro,
            website=website,
            buy_signal_score=buy_signal,
            qualification_tier=tier,
            qualification_score=q_score,
            reason=reason,
            enrichment_attempts=attempts,
            priority_score=priority,
            priority_reasons=priority_reasons,
            closer_brief=brief,
            voice_legal_basis=voice_legal_basis,
            line_type=line_type,
            legal_basis_source=legal_basis_source,
        ))

    items.sort(
        key=lambda item: (
            -item.priority_score,
            item.enrichment_attempts,
            item.business_name.lower(),
        )
    )
    selected = items[:bounded]
    transport = VonageCallTransport(VonageCallConfig.from_env())
    provider_readiness = transport.config.readiness()
    previews = {
        item.prospect_id: transport.preview(item.as_dict())
        for item in selected
    }
    return {
        "schema_version": "empire.call_manager.v1",
        "mode": "PREPARE_ONLY",
        "provider": "vonage",
        "channel": "voice",
        "queue_total": len(items),
        "selected": len(selected),
        "items": [
            {
                **item.as_dict(),
                "provider_preview": previews[item.prospect_id],
            }
            for item in selected
        ],
        "provider_readiness": provider_readiness,
        "live_calls_placed": 0,
        "execution_allowed": False,
        "requires_live_call_authority": True,
        "conversation_os_ready": True,
        "actual_revenue": False,
    }


def write_call_work_snapshot(
    result: Mapping[str, Any],
    path: str | Path = "/srv/empire_os/runtime/closer/call_manager_latest.json",
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target
