"""Governed policy boundary for Recall-backed SHADOW meeting joins."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import time
from typing import Any

from empire_os.recall_shadow_bot_client import (
    RecallBotCreateResult,
    RecallShadowJoinAuthorization,
    RecallTransport,
    create_recall_shadow_bot,
)
from empire_os.recall_shadow_bot_plan import RecallShadowBotPlan


_ALLOWED_REGIONS = {
    "us-west-2",
    "us-east-1",
    "eu-central-1",
    "ap-northeast-1",
}


def _dt(value: str) -> datetime:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("approval timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("approval timestamps must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RecallShadowJoinApproval:
    meeting_id: str
    approved_by: str
    approval_evidence_ref: str
    approved_at: str
    expires_at: str
    allow_adhoc: bool = False

    def validate(self, *, now: str) -> None:
        if not self.meeting_id.strip():
            raise ValueError("approved meeting_id required")
        if not self.approved_by.strip():
            raise ValueError("approved_by required")
        if not self.approval_evidence_ref.strip():
            raise ValueError("live join approval evidence required")
        approved = _dt(self.approved_at)
        expires = _dt(self.expires_at)
        current = _dt(now)
        if expires <= approved:
            raise ValueError("live join approval expiry invalid")
        if current < approved or current >= expires:
            raise ValueError("live join approval not active")

    def to_provider_authorization(self) -> RecallShadowJoinAuthorization:
        return RecallShadowJoinAuthorization(
            approval_evidence_ref=self.approval_evidence_ref,
            meeting_id=self.meeting_id,
            approved_by=self.approved_by,
            approved_at=self.approved_at,
            expires_at=self.expires_at,
            allow_adhoc=self.allow_adhoc,
        )


@dataclass(frozen=True)
class AuthorizedRecallShadowJoin:
    plan: RecallShadowBotPlan
    region: str
    authorization: RecallShadowJoinAuthorization
    live_join_authorized: bool = True
    speech_execution: bool = False
    chat_send_execution: bool = False
    commercial_execution: bool = False
    execution_authority: str = "shadow_join_only"

    @property
    def meeting_id(self) -> str:
        return self.plan.meeting_id

    @property
    def avatar_id(self) -> str:
        return self.plan.avatar_id

    @property
    def endpoint(self) -> str:
        return f"https://{self.region}.recall.ai/api/v1/bot/"

    @property
    def request_body(self) -> dict[str, Any]:
        return dict(self.plan.request_body)

    @property
    def approval_evidence_ref(self) -> str:
        return self.authorization.approval_evidence_ref

    def as_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "avatar_id": self.avatar_id,
            "region": self.region,
            "endpoint": self.endpoint,
            "request_body": self.request_body,
            "approval_evidence_ref": self.approval_evidence_ref,
            "authorization": asdict(self.authorization),
            "live_join_authorized": self.live_join_authorized,
            "speech_execution": self.speech_execution,
            "chat_send_execution": self.chat_send_execution,
            "commercial_execution": self.commercial_execution,
            "execution_authority": self.execution_authority,
        }


def prepare_recall_shadow_join(
    *,
    plan: RecallShadowBotPlan,
    approval: RecallShadowJoinApproval,
    region: str,
    now: str,
) -> AuthorizedRecallShadowJoin:
    if plan.mode != "SHADOW":
        raise ValueError("Recall live join requires SHADOW plan")
    if plan.output_media_enabled or plan.speech_execution or plan.chat_send_enabled:
        raise ValueError("SHADOW plan cannot contain output execution")
    if plan.execution_authority != "none":
        raise ValueError("SHADOW plan cannot contain business authority")

    approval.validate(now=now)
    if approval.meeting_id != plan.meeting_id:
        raise ValueError("live join approval meeting mismatch")

    clean_region = str(region or "").strip()
    if clean_region not in _ALLOWED_REGIONS:
        raise ValueError("unsupported Recall region")

    provider_auth = approval.to_provider_authorization()
    provider_auth.validate(
        plan=plan,
        now=_dt(now),
    )
    return AuthorizedRecallShadowJoin(
        plan=plan,
        region=clean_region,
        authorization=provider_auth,
    )


def execute_recall_shadow_join(
    *,
    request: AuthorizedRecallShadowJoin,
    api_key: str,
    transport: RecallTransport | None = None,
    sleeper=time.sleep,
    now: datetime | None = None,
    timeout_s: float = 20.0,
    max_attempts: int = 10,
) -> dict[str, Any]:
    if request.live_join_authorized is not True:
        raise ValueError("live join authorization required")
    if (
        request.speech_execution
        or request.chat_send_execution
        or request.commercial_execution
    ):
        raise ValueError("SHADOW join cannot enable output/commercial execution")

    result: RecallBotCreateResult = create_recall_shadow_bot(
        plan=request.plan,
        region=request.region,
        api_key=api_key,
        authorization=request.authorization,
        transport=transport,
        sleeper=sleeper,
        now=now,
        timeout_s=timeout_s,
        max_attempts=max_attempts,
    )
    return {
        **result.as_dict(),
        "provider": "recall",
        "meeting_id": request.meeting_id,
        "avatar_id": request.avatar_id,
        "approval_evidence_ref": request.approval_evidence_ref,
        "live_join_performed": result.meeting_join_requested,
        "chat_send_execution": result.chat_execution,
    }
