"""Durable deferred enrichment and governed call-ready fallback.

Unresolved buyers remain eligible for later first-party enrichment.  A phone
number may be promoted to a call-ready *review* queue only after a deeper
enrichment pass still cannot produce review-ready email evidence.  This module
never places calls and never expands outbound authority.
"""
from __future__ import annotations

import fcntl
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.buyer_discovery import looks_like_person_name

from empire_os.phone_quality import (
    is_commercially_usable_phone,
    normalized_e164,
    phone_digits,
)

DEFERRED_PATH = Path(
    "/srv/empire_os/runtime/hunter/buyer_deferred_enrichment.json"
)
CALL_READY_PATH = Path(
    "/srv/empire_os/runtime/closer/call_ready.json"
)

DEFERABLE_REASONS = frozenset({
    "site_unavailable",
    "site_timeout",
    "no_decision_maker",
    "no_contact_evidence",
    "no_bound_contact",
    "contact_not_verified",
    "outreach_not_ready",
    "decision_maker_missing",
    "decision_score_below_floor",
    "target_contact_not_verified",
    "target_identity_mismatch",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).astimezone(timezone.utc).isoformat()


def _parse(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _locked_update(path: Path, fn):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    lock.touch(exist_ok=True)
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = _load(path)
            result = fn(data)
            _atomic_write(path, data)
            return result
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)




def _priority(value: Any, *, default: int = 50) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = int(default)
    return max(0, min(score, 100))


def _effective_priority(item: Mapping[str, Any], *, now: datetime) -> int:
    base = _priority(item.get("priority_score"))
    created = _parse(item.get("created_at")) or now
    age_hours = max(0, int((now - created).total_seconds() // 3600))
    attempts = max(0, int(item.get("attempts") or 0))
    reason = str(item.get("reason") or "").strip()

    target_people = [
        row for row in (item.get("target_people") or [])
        if isinstance(row, Mapping)
        and looks_like_person_name(row.get("name"))
        and str(row.get("title") or "").strip()
    ]
    verified_routes = [
        row for row in (item.get("company_contact_routes") or [])
        if isinstance(row, Mapping)
        and row.get("verified") is True
        and str(row.get("value") or "").strip()
    ]

    evidence_bonus = min(24, len(target_people) * 6) + min(
        16, len(verified_routes) * 4
    )
    if str(item.get("offer_key") or "").strip():
        evidence_bonus += 8
    if str(item.get("wave") or "").strip() in {
        "buyer_scout_review_ready",
        "rolling_enterprise",
        "direct_enterprise",
    }:
        evidence_bonus += 6

    near_sendable = bool(target_people) and reason in {
        "no_contact_evidence",
        "no_bound_contact",
        "contact_not_verified",
        "outreach_not_ready",
        "target_contact_not_verified",
    }
    conversion_proximity_bonus = (
        32 + min(8, len(verified_routes) * 4)
        if near_sendable
        else 0
    )
    attempt_penalty = (
        min(40, attempts * 2)
        if near_sendable
        else min(80, attempts * 4)
    )
    weak_reason_penalty = (
        30
        if reason in {
            "site_unavailable",
            "site_timeout",
            "network_probe_budget_exhausted",
        }
        else 0
    )

    # Fourteen-day starvation protection remains stronger than the adaptive
    # evidence and retry policy.
    starvation_boost = 1000 if age_hours >= 24 * 14 else 0
    return (
        starvation_boost
        + base
        + evidence_bonus
        + conversion_proximity_bonus
        - attempt_penalty
        - weak_reason_penalty
    )

def canonical_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if not is_commercially_usable_phone(raw):
        return ""
    direct = normalized_e164(raw)
    if direct:
        return direct
    digits = phone_digits(raw)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ""


class BuyerDeferredEnrichmentQueue:
    def __init__(
        self,
        *,
        deferred_path: str | Path = DEFERRED_PATH,
        call_ready_path: str | Path = CALL_READY_PATH,
    ) -> None:
        self.deferred_path = Path(deferred_path)
        self.call_ready_path = Path(call_ready_path)

    def enqueue(self, item: Mapping[str, Any]) -> bool:
        prospect_id = str(item.get("prospect_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not prospect_id or reason not in DEFERABLE_REASONS:
            return False

        def mutate(data: dict[str, dict[str, Any]]) -> bool:
            existing = data.get(prospect_id)
            now = _iso()
            if not isinstance(existing, dict):
                existing = {
                    "prospect_id": prospect_id,
                    "created_at": now,
                    "attempts": 0,
                }
            target_people = [
                {
                    "name": str(person.get("name") or "").strip(),
                    "title": str(person.get("title") or "").strip(),
                    "source": (
                        str(person.get("source") or "").strip() or None
                    ),
                    "evidence_url": (
                        str(person.get("evidence_url") or "").strip() or None
                    ),
                }
                for person in (item.get("target_people") or [])
                if isinstance(person, Mapping)
                and looks_like_person_name(person.get("name"))
                and str(person.get("title") or "").strip()
            ][:6]
            target_product_codes = [
                str(value).strip()
                for value in (item.get("target_product_codes") or [])
                if str(value).strip()
            ][:6]
            company_contact_routes = [
                dict(route)
                for route in (item.get("company_contact_routes") or [])
                if isinstance(route, Mapping)
                and route.get("verified") is True
                and str(route.get("value") or "").strip()
            ][:8]

            requested_priority = _priority(
                item.get("priority_score"),
                default=_priority(existing.get("priority_score")),
            )
            existing_priority = _priority(existing.get("priority_score"))
            existing.update({
                "business_name": str(item.get("business_name") or "").strip(),
                "website": str(item.get("website") or "").strip(),
                "phone": (
                    str(item.get("phone") or "").strip()
                    or str(existing.get("phone") or "").strip()
                ),
                "entity_id": (
                    str(item.get("entity_id") or "").strip()
                    or existing.get("entity_id")
                    or None
                ),
                "reason": reason,
                "status": "pending",
                "updated_at": now,
                "next_retry_at": existing.get("next_retry_at") or now,
                "account_key": (
                    str(item.get("account_key") or "").strip()
                    or existing.get("account_key")
                    or None
                ),
                "wave": (
                    str(item.get("wave") or "").strip()
                    or existing.get("wave")
                    or None
                ),
                "offer_key": (
                    str(item.get("offer_key") or "").strip()
                    or existing.get("offer_key")
                    or None
                ),
                "target_people": (
                    target_people
                    or list(existing.get("target_people") or [])
                ),
                "target_product_codes": (
                    target_product_codes
                    or list(existing.get("target_product_codes") or [])
                ),
                "company_contact_routes": (
                    company_contact_routes
                    or list(existing.get("company_contact_routes") or [])
                ),
                "priority_score": max(existing_priority, requested_priority),
                "priority_reason": (
                    str(item.get("priority_reason") or "").strip()
                    or existing.get("priority_reason")
                    or "default"
                ),
            })
            data[prospect_id] = existing
            return True

        return bool(_locked_update(self.deferred_path, mutate))

    def due(
        self,
        *,
        limit: int = 10,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = (now or _now()).astimezone(timezone.utc)
        rows = []
        for item in _load(self.deferred_path).values():
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") not in {"pending", "deferred"}:
                continue
            retry_at = _parse(item.get("next_retry_at"))
            if retry_at is not None and retry_at > current:
                continue
            rows.append(dict(item))
        rows.sort(
            key=lambda row: (
                -_effective_priority(row, now=current),
                -_priority(row.get("priority_score")),
                int(row.get("attempts") or 0),
                str(row.get("created_at") or ""),
                str(row.get("prospect_id") or ""),
            )
        )
        return rows[: max(1, min(int(limit), 25))]

    def claim_due(
        self,
        *,
        limit: int = 10,
        worker_id: str,
        lease_seconds: int = 420,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        owner = str(worker_id or "").strip()
        if not owner:
            raise ValueError("worker_id required")
        current = (now or _now()).astimezone(timezone.utc)
        safe_limit = max(1, min(int(limit), 25))
        safe_lease = max(60, min(int(lease_seconds), 1800))

        def mutate(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for row in data.values():
                if not isinstance(row, dict):
                    continue
                status = str(row.get("status") or "")
                if status == "running":
                    lease_expires = _parse(row.get("lease_expires_at"))
                    if lease_expires is not None and lease_expires <= current:
                        row.update({
                            "status": "deferred",
                            "lease_owner": None,
                            "lease_expires_at": None,
                            "updated_at": _iso(current),
                        })
                        status = "deferred"
                if status not in {"pending", "deferred"}:
                    continue
                retry_at = _parse(row.get("next_retry_at"))
                if retry_at is not None and retry_at > current:
                    continue
                rows.append(row)

            rows.sort(
                key=lambda row: (
                    -_effective_priority(row, now=current),
                    -_priority(row.get("priority_score")),
                    int(row.get("attempts") or 0),
                    str(row.get("created_at") or ""),
                    str(row.get("prospect_id") or ""),
                )
            )
            selected = rows[:safe_limit]
            expires = _iso(current + timedelta(seconds=safe_lease))
            claimed: list[dict[str, Any]] = []
            for row in selected:
                row.update({
                    "status": "running",
                    "lease_owner": owner,
                    "lease_expires_at": expires,
                    "updated_at": _iso(current),
                })
                claimed.append(dict(row))
            return claimed

        return list(_locked_update(self.deferred_path, mutate))

    def defer_again(
        self,
        prospect_id: str,
        *,
        reason: str,
        attempts: int,
        retry_minutes: int,
    ) -> None:
        def mutate(data: dict[str, dict[str, Any]]) -> None:
            row = data.get(prospect_id)
            if not isinstance(row, dict):
                return
            now = _now()
            row.update({
                "reason": reason,
                "attempts": max(int(attempts), int(row.get("attempts") or 0)),
                "status": "deferred",
                "last_attempt_at": _iso(now),
                "updated_at": _iso(now),
                "next_retry_at": _iso(
                    now + timedelta(minutes=max(5, int(retry_minutes)))
                ),
                "lease_owner": None,
                "lease_expires_at": None,
            })
        _locked_update(self.deferred_path, mutate)

    def resolve(self, prospect_id: str, *, outcome: str) -> None:
        def mutate(data: dict[str, dict[str, Any]]) -> None:
            row = data.get(prospect_id)
            if not isinstance(row, dict):
                return
            row.update({
                "status": "resolved",
                "outcome": str(outcome or "resolved"),
                "updated_at": _iso(),
                "next_retry_at": None,
                "lease_owner": None,
                "lease_expires_at": None,
            })
        _locked_update(self.deferred_path, mutate)

    def mark_call_ready(
        self,
        item: Mapping[str, Any],
        *,
        reason: str,
        enrichment_attempts: int,
    ) -> bool:
        prospect_id = str(item.get("prospect_id") or "").strip()
        phone = canonical_phone(item.get("phone"))
        if not prospect_id or not phone:
            return False

        def mutate(data: dict[str, dict[str, Any]]) -> bool:
            now = _iso()
            row = data.get(prospect_id)
            if not isinstance(row, dict):
                row = {
                    "prospect_id": prospect_id,
                    "created_at": now,
                }
            row.update({
                "business_name": str(item.get("business_name") or "").strip(),
                "phone": phone,
                "website": str(item.get("website") or "").strip(),
                "entity_id": str(item.get("entity_id") or "").strip() or None,
                "reason": str(reason or "email_enrichment_exhausted"),
                "enrichment_attempts": max(1, int(enrichment_attempts)),
                "status": "ready_for_review",
                "channel": "phone",
                "execution_allowed": False,
                "requires_live_call_authority": True,
                "source": "buyer_deferred_enrichment",
                "voice_legal_basis": (
                    str(item.get("voice_legal_basis") or "").strip() or None
                ),
                "line_type": (
                    str(item.get("line_type") or "").strip() or None
                ),
                "legal_basis_source": (
                    str(item.get("legal_basis_source") or "").strip() or None
                ),
                "updated_at": now,
            })
            data[prospect_id] = row
            return True

        return bool(_locked_update(self.call_ready_path, mutate))

    def mark_call_attempted(
        self,
        prospect_id: str,
        *,
        intent_id: str,
        provider_call_id: str,
    ) -> None:
        def mutate(data: dict[str, dict[str, Any]]) -> None:
            row = data.get(prospect_id)
            if not isinstance(row, dict):
                return
            row.update({
                "status": "call_attempted",
                "intent_id": str(intent_id or "").strip() or None,
                "provider_call_id": (
                    str(provider_call_id or "").strip() or None
                ),
                "last_call_attempt_at": _iso(),
                "updated_at": _iso(),
                "execution_allowed": False,
            })
        _locked_update(self.call_ready_path, mutate)

    def snapshot(self) -> dict[str, Any]:
        deferred = _load(self.deferred_path)
        calls = _load(self.call_ready_path)
        counts: dict[str, int] = {}
        current = _now()
        pending_ages: list[float] = []
        due_now = 0
        for row in deferred.values():
            if isinstance(row, dict):
                status = str(row.get("status") or "unknown")
                counts[status] = counts.get(status, 0) + 1
                if status == "pending":
                    created = _parse(row.get("created_at"))
                    if created is not None:
                        pending_ages.append(
                            max(0.0, (current - created).total_seconds() / 3600)
                        )
                if status in {"pending", "deferred"}:
                    retry_at = _parse(row.get("next_retry_at"))
                    if retry_at is None or retry_at <= current:
                        due_now += 1
        oldest_pending_hours = max(pending_ages, default=0.0)
        stale_pending_count = sum(age >= 6.0 for age in pending_ages)
        pending_count = int(counts.get("pending") or 0)
        backlog_health = (
            "CRITICAL"
            if oldest_pending_hours >= 24.0 or pending_count >= 1500
            else "DEGRADED"
            if oldest_pending_hours >= 6.0 or pending_count >= 500
            else "HEALTHY"
        )
        return {
            "deferred_total": len(deferred),
            "deferred_by_status": counts,
            "due_now": due_now,
            "oldest_pending_hours": round(oldest_pending_hours, 2),
            "stale_pending_count": stale_pending_count,
            "backlog_health": backlog_health,
            "call_ready_total": sum(
                1 for row in calls.values()
                if isinstance(row, dict)
                and row.get("status") == "ready_for_review"
            ),
            "execution_allowed": False,
        }
