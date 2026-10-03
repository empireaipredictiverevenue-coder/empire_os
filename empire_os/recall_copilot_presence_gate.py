"""Human-gated Recall Output Media start/stop for Digital Avatar COPILOT."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import time
from typing import Any, Mapping, Protocol
import urllib.error
import urllib.request

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.recall_copilot_output_media import RecallCopilotOutputMediaPlan


def _dt(value: str) -> datetime:
    raw = str(value or "").strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("presence approval timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("presence approval timestamps must include timezone")
    return parsed.astimezone(timezone.utc)


def output_media_plan_sha256(plan: RecallCopilotOutputMediaPlan) -> str:
    encoded = json.dumps(
        plan.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecallCopilotPresenceApproval:
    meeting_id: str
    avatar_id: str
    bot_id: str
    approved_by: str
    approval_evidence_ref: str
    approved_at: str
    expires_at: str
    plan_sha256: str

    def validate(
        self,
        *,
        identity: DigitalAvatarIdentity,
        plan: RecallCopilotOutputMediaPlan,
        now: datetime,
    ) -> None:
        if self.meeting_id != plan.meeting_id:
            raise ValueError("presence approval meeting mismatch")
        if self.avatar_id != plan.avatar_id:
            raise ValueError("presence approval avatar mismatch")
        if self.bot_id != plan.bot_id:
            raise ValueError("presence approval bot mismatch")
        if self.approved_by.strip() != identity.owner_name.strip():
            raise ValueError("presence approval owner mismatch")
        if not self.approval_evidence_ref.strip():
            raise ValueError("presence approval evidence required")
        if self.plan_sha256 != output_media_plan_sha256(plan):
            raise ValueError("presence approval plan fingerprint mismatch")
        approved = _dt(self.approved_at)
        expires = _dt(self.expires_at)
        current = now.astimezone(timezone.utc)
        if expires <= approved:
            raise ValueError("presence approval expiry invalid")
        if current < approved or current >= expires:
            raise ValueError("presence approval not active")
        if int(current.timestamp()) >= plan.presence_token_expires_at:
            raise ValueError("presence session token expired")
        if plan.presence_runtime_audio_locked is not True:
            raise ValueError("presence runtime must start audio-locked")
        if plan.per_turn_speech_approval_required is not True:
            raise ValueError("presence runtime must require per-turn speech approval")


@dataclass(frozen=True)
class AuthorizedRecallCopilotPresenceStart:
    plan: RecallCopilotOutputMediaPlan
    approval: RecallCopilotPresenceApproval
    output_media_start_allowed: bool = True
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "copilot_presence_start_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.as_dict(),
            "approval": asdict(self.approval),
            "output_media_start_allowed": self.output_media_start_allowed,
            "speech_execution_allowed": self.speech_execution_allowed,
            "commercial_execution_allowed": self.commercial_execution_allowed,
            "execution_authority": self.execution_authority,
        }


def authorize_recall_copilot_presence_start(
    *,
    identity: DigitalAvatarIdentity,
    plan: RecallCopilotOutputMediaPlan,
    approval: RecallCopilotPresenceApproval,
    now: datetime | None = None,
) -> AuthorizedRecallCopilotPresenceStart:
    identity.validate()
    current = now or datetime.now(timezone.utc)
    approval.validate(identity=identity, plan=plan, now=current)
    if plan.output_media_start_allowed:
        raise ValueError("Output Media plan unexpectedly carries start authority")
    if plan.speech_execution_allowed or plan.commercial_execution_allowed:
        raise ValueError("Output Media plan grants forbidden execution")
    return AuthorizedRecallCopilotPresenceStart(
        plan=plan,
        approval=approval,
    )


class RecallOutputMediaTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        ...

    def delete_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        ...


class UrllibRecallOutputMediaTransport:
    def _request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method=method,
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

    def post_json(self, **kwargs):
        return self._request(method="POST", **kwargs)

    def delete_json(self, **kwargs):
        return self._request(method="DELETE", **kwargs)


def _headers(api_key: str) -> dict[str, str]:
    clean_key = str(api_key or "").strip()
    if not clean_key:
        raise ValueError("Recall API key required")
    return {
        "Authorization": f"Token {clean_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def start_recall_copilot_presence(
    *,
    authorization: AuthorizedRecallCopilotPresenceStart,
    identity: DigitalAvatarIdentity,
    api_key: str,
    transport: RecallOutputMediaTransport | None = None,
    now: datetime | None = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    authorization.approval.validate(
        identity=identity,
        plan=authorization.plan,
        now=current,
    )
    if authorization.output_media_start_allowed is not True:
        raise ValueError("Output Media start authorization required")
    if authorization.speech_execution_allowed:
        raise ValueError("Presence start cannot grant speech execution")
    client = transport or UrllibRecallOutputMediaTransport()
    status, _response_headers, _body = client.post_json(
        url=authorization.plan.endpoint,
        headers=_headers(api_key),
        payload=authorization.plan.request_body,
        timeout_s=timeout_s,
    )
    if status != 200:
        raise RuntimeError(f"Recall Output Media start failed with status {status}")
    return {
        "meeting_id": authorization.plan.meeting_id,
        "avatar_id": authorization.plan.avatar_id,
        "bot_id": authorization.plan.bot_id,
        "provider": "recall",
        "provider_status": status,
        "presence_active": True,
        "output_media_start_performed": True,
        "speech_execution_allowed": False,
        "commercial_execution_allowed": False,
        "execution_authority": "copilot_presence_start_only",
    }


def stop_recall_copilot_presence(
    *,
    authorization: AuthorizedRecallCopilotPresenceStart,
    api_key: str,
    transport: RecallOutputMediaTransport | None = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    client = transport or UrllibRecallOutputMediaTransport()
    status, _response_headers, _body = client.delete_json(
        url=authorization.plan.endpoint,
        headers=_headers(api_key),
        payload={"camera": True},
        timeout_s=timeout_s,
    )
    if status not in {200, 204}:
        raise RuntimeError(f"Recall Output Media stop failed with status {status}")
    return {
        "meeting_id": authorization.plan.meeting_id,
        "avatar_id": authorization.plan.avatar_id,
        "bot_id": authorization.plan.bot_id,
        "provider": "recall",
        "provider_status": status,
        "presence_active": False,
        "output_media_stop_performed": True,
        "speech_execution_allowed": False,
        "commercial_execution_allowed": False,
        "execution_authority": "presence_stop_only",
    }
