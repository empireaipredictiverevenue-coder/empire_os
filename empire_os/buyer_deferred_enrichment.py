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
            existing.update({
                "business_name": str(item.get("business_name") or "").strip(),
                "website": str(item.get("website") or "").strip(),
                "phone": str(item.get("phone") or "").strip(),
                "entity_id": str(item.get("entity_id") or "").strip() or None,
                "reason": reason,
                "status": "pending",
                "updated_at": now,
                "next_retry_at": existing.get("next_retry_at") or now,
                "account_key": (
                    str(item.get("account_key") or "").strip() or None
                ),
                "wave": str(item.get("wave") or "").strip() or None,
                "offer_key": (
                    str(item.get("offer_key") or "").strip() or None
                ),
                "target_people": [
                    {
                        "name": str(person.get("name") or "").strip(),
                        "title": str(person.get("title") or "").strip(),
                    }
                    for person in (item.get("target_people") or [])
                    if isinstance(person, Mapping)
                    and str(person.get("name") or "").strip()
                    and str(person.get("title") or "").strip()
                ][:6],
                "target_product_codes": [
                    str(value).strip()
                    for value in (item.get("target_product_codes") or [])
                    if str(value).strip()
                ][:6],
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
                int(row.get("attempts") or 0),
                str(row.get("created_at") or ""),
            )
        )
        return rows[: max(1, min(int(limit), 25))]

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
        for row in deferred.values():
            if isinstance(row, dict):
                status = str(row.get("status") or "unknown")
                counts[status] = counts.get(status, 0) + 1
        return {
            "deferred_total": len(deferred),
            "deferred_by_status": counts,
            "call_ready_total": sum(
                1 for row in calls.values()
                if isinstance(row, dict)
                and row.get("status") == "ready_for_review"
            ),
            "execution_allowed": False,
        }
