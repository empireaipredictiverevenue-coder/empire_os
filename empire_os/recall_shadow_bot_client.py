"""Governed Recall Create Bot client for Digital Avatar SHADOW meetings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, Callable, Mapping, Protocol
import urllib.error
import urllib.request

from empire_os.recall_shadow_bot_plan import RecallShadowBotPlan


_ALLOWED_REGIONS = {
    "us-west-2",
    "us-east-1",
    "eu-central-1",
    "ap-northeast-1",
}


@dataclass(frozen=True)
class RecallShadowJoinAuthorization:
    approval_evidence_ref: str
    meeting_id: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    expires_at: str | None = None
    allow_adhoc: bool = False

    def validate(
        self,
        *,
        plan: RecallShadowBotPlan | None = None,
        now: datetime | None = None,
    ) -> None:
        if not str(self.approval_evidence_ref or "").strip():
            raise ValueError("explicit shadow join approval evidence required")
        if self.meeting_id is not None:
            if plan is None:
                raise ValueError("meeting-bound approval requires bot plan")
            if str(self.meeting_id).strip() != plan.meeting_id:
                raise ValueError("shadow join approval meeting mismatch")

        window_values = (
            self.approved_by,
            self.approved_at,
            self.expires_at,
        )
        if any(value is not None for value in window_values):
            if not all(str(value or "").strip() for value in window_values):
                raise ValueError("complete time-bounded join approval required")
            approved = _approval_time(str(self.approved_at))
            expires = _approval_time(str(self.expires_at))
            current = now or datetime.now(timezone.utc)
            current = current.astimezone(timezone.utc)
            if expires <= approved:
                raise ValueError("shadow join approval expiry invalid")
            if current < approved or current >= expires:
                raise ValueError("shadow join approval not active")


@dataclass(frozen=True)
class RecallBotCreateResult:
    bot_id: str
    region: str
    attempts: int
    scheduled: bool
    provider_status: int
    meeting_join_requested: bool = True
    speech_execution: bool = False
    chat_execution: bool = False
    commercial_execution: bool = False
    execution_authority: str = "shadow_join_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecallTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        ...


class UrllibRecallTransport:
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                body = json.loads(raw) if raw else {}
                return response.status, dict(response.headers), body
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw[:1000]}
            return exc.code, dict(exc.headers), body


def _approval_time(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("approval timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("approval timestamps must include timezone")
    return parsed.astimezone(timezone.utc)


def _join_at(plan: RecallShadowBotPlan) -> datetime | None:
    raw = plan.request_body.get("join_at")
    if not raw:
        return None
    value = str(raw)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("Recall join_at must include timezone")
    return parsed.astimezone(timezone.utc)


def _scheduled(
    plan: RecallShadowBotPlan,
    *,
    now: datetime,
) -> bool:
    join_at = _join_at(plan)
    if join_at is None:
        return False
    current = now.astimezone(timezone.utc)
    return (join_at - current).total_seconds() >= 600


def create_recall_shadow_bot(
    *,
    plan: RecallShadowBotPlan,
    region: str,
    api_key: str,
    authorization: RecallShadowJoinAuthorization,
    transport: RecallTransport | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
    timeout_s: float = 20.0,
    max_attempts: int = 10,
) -> RecallBotCreateResult:
    current = now or datetime.now(timezone.utc)
    authorization.validate(plan=plan, now=current)
    clean_region = str(region or "").strip()
    clean_key = str(api_key or "").strip()
    if clean_region not in _ALLOWED_REGIONS:
        raise ValueError("unsupported Recall region")
    if not clean_key:
        raise ValueError("Recall API key required")
    if plan.mode != "SHADOW" or plan.execution_authority != "none":
        raise ValueError("Recall Create Bot requires non-executing SHADOW plan")
    if plan.output_media_enabled or plan.chat_send_enabled or plan.speech_execution:
        raise ValueError("SHADOW plan cannot enable output media, chat or speech")
    if max_attempts < 1 or max_attempts > 10:
        raise ValueError("max_attempts must be between 1 and 10")


    scheduled = _scheduled(plan, now=current)
    if not scheduled and not authorization.allow_adhoc:
        raise ValueError("ad-hoc Recall join requires explicit allow_adhoc authority")

    client = transport or UrllibRecallTransport()
    url = f"https://{clean_region}.recall.ai/api/v1/bot/"
    headers = {
        "Authorization": f"Token {clean_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_attempts + 1):
        status, response_headers, body = client.post_json(
            url=url,
            headers=headers,
            payload=plan.request_body,
            timeout_s=timeout_s,
        )
        if status == 201:
            bot_id = str(body.get("id") or "").strip()
            if not bot_id:
                raise RuntimeError("Recall Create Bot response missing bot id")
            return RecallBotCreateResult(
                bot_id=bot_id,
                region=clean_region,
                attempts=attempt,
                scheduled=scheduled,
                provider_status=status,
            )

        if status == 507 and attempt < max_attempts:
            raw_delay = response_headers.get("Retry-After") or response_headers.get(
                "retry-after"
            )
            try:
                delay = float(raw_delay) if raw_delay is not None else 30.0
            except (TypeError, ValueError):
                delay = 30.0
            sleeper(max(0.0, delay))
            continue

        raise RuntimeError(f"Recall Create Bot failed with status {status}")

    raise RuntimeError("Recall Create Bot exhausted retry attempts")
