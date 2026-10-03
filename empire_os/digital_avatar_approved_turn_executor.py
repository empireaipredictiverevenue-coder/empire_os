"""Execute exactly one human-approved Digital Avatar COPILOT speech turn."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Protocol
import urllib.error
import urllib.request
from urllib.parse import urlparse

from empire_os.digital_avatar import (
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_copilot import AvatarCopilotHandoff
from empire_os.digital_avatar_speech import (
    AvatarHumanTurnApproval,
    build_avatar_speech_render_task,
)
from empire_os.digital_avatar_speech_transmission import (
    authorize_avatar_speech_transmission,
    claim_speech_transmission_ticket,
    finalize_inflight_speech_transmission_record,
    materialize_speech_transmission_ticket,
)
from empire_os.digital_avatar_voice_profile import (
    AvatarVoiceProfile,
    build_avatar_voice_render_plan,
)
from empire_os.digital_avatar_voice_sidecar import (
    AvatarVoiceSidecarConfig,
    VoiceSidecarStreamTransport,
    build_voice_sidecar_request,
    render_voice_sidecar_pcm,
)


@dataclass(frozen=True)
class PresenceAudioPushConfig:
    url: str
    secret: str
    timeout_s: float = 90.0
    max_audio_bytes: int = 12_000_000

    def validate(self) -> None:
        parsed = urlparse(str(self.url or "").strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Presence audio push URL scheme invalid")
        host = (parsed.hostname or "").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Presence audio push must remain loopback-only")
        if parsed.path != "/internal/avatar/presence/audio":
            raise ValueError("Presence audio push path invalid")
        if len(str(self.secret or "").encode("utf-8")) < 32:
            raise ValueError("Presence audio push secret must be at least 32 bytes")
        if self.timeout_s <= 0 or self.timeout_s > 180:
            raise ValueError("Presence audio push timeout invalid")
        if self.max_audio_bytes <= 0:
            raise ValueError("Presence audio max bytes invalid")


class PresenceAudioPushTransport(Protocol):
    def post_pcm(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
    ) -> tuple[int, Mapping[str, Any]]:
        ...


class UrllibPresenceAudioPushTransport:
    def post_pcm(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_s: float,
    ) -> tuple[int, Mapping[str, Any]]:
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
                if not isinstance(payload, Mapping):
                    payload = {"raw": raw[:1000]}
                return response.status, dict(payload)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            if not isinstance(payload, Mapping):
                payload = {"raw": raw[:1000]}
            return exc.code, dict(payload)


@dataclass(frozen=True)
class ApprovedAvatarTurnExecution:
    meeting_id: str
    avatar_id: str
    ticket_id: str
    audio_sha256: str
    pcm_bytes: int
    sample_rate: int
    state: str
    browser_playback_completed: bool
    speech_transmission_performed: bool
    meeting_audio_delivery_verified: bool = False
    raw_audio_persisted: bool = False
    autonomous_speech_execution: bool = False
    chat_execution: bool = False
    commercial_execution: bool = False
    payment_execution: bool = False
    execution_authority: str = "approved_turn_audio_only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _record(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("speech transmission record unreadable") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("speech transmission record invalid")
    return raw


def _reconcile_ambiguous_push(
    *,
    ticket_path: Path,
    ticket_id: str,
    now: datetime,
    error_code: str,
) -> str:
    try:
        final = finalize_inflight_speech_transmission_record(
            path=ticket_path,
            ticket_id=ticket_id,
            performed=False,
            now=now,
            error_code=error_code,
        )
        return str(final.get("state") or "reconciliation_required")
    except ValueError:
        current = _record(ticket_path)
        state = str(current.get("state") or "")
        if state in {"completed", "reconciliation_required"}:
            return state
        raise


def execute_approved_avatar_turn(
    *,
    identity: DigitalAvatarIdentity,
    session: AvatarMeetingSession,
    handoff: AvatarCopilotHandoff,
    approval: AvatarHumanTurnApproval,
    voice_profile: AvatarVoiceProfile,
    voice_sidecar_config: AvatarVoiceSidecarConfig,
    presence_state: Mapping[str, Any],
    speech_ticket_root: str | Path,
    presence_push: PresenceAudioPushConfig,
    available_voice_engines: Mapping[str, bool],
    now: datetime | None = None,
    voice_transport: VoiceSidecarStreamTransport | None = None,
    presence_transport: PresenceAudioPushTransport | None = None,
) -> ApprovedAvatarTurnExecution:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    presence_push.validate()

    task = build_avatar_speech_render_task(
        identity=identity,
        session=session,
        handoff=handoff,
        approval=approval,
        now=current,
    )
    plan = build_avatar_voice_render_plan(
        task=task,
        profile=voice_profile,
        available_engines=available_voice_engines,
    )
    render_request = build_voice_sidecar_request(task=task, plan=plan)

    pcm = bytearray()
    artifact = render_voice_sidecar_pcm(
        config=voice_sidecar_config,
        request=render_request,
        on_chunk=pcm.extend,
        transport=voice_transport,
    )
    if artifact.pcm_bytes != len(pcm):
        raise RuntimeError("rendered PCM size evidence mismatch")
    if len(pcm) > presence_push.max_audio_bytes:
        raise RuntimeError("rendered PCM exceeds Presence push limit")

    ticket = authorize_avatar_speech_transmission(
        identity=identity,
        task=task,
        artifact=artifact,
        approval=approval,
        presence_state=presence_state,
        now=current,
    )
    ticket_path = materialize_speech_transmission_ticket(
        root=speech_ticket_root,
        ticket=ticket,
    )
    claim_speech_transmission_ticket(
        path=ticket_path,
        ticket=ticket,
        now=current,
    )

    headers = {
        "Authorization": "Bearer " + presence_push.secret,
        "Content-Type": "application/octet-stream",
        "X-Empire-Ticket-Id": ticket.ticket_id,
        "X-Empire-Meeting-Id": ticket.meeting_id,
        "X-Empire-Avatar-Id": ticket.avatar_id,
        "X-Empire-Bot-Id": ticket.bot_id,
        "X-Empire-Audio-Sha256": ticket.audio_sha256,
        "X-Empire-Sample-Rate": str(ticket.sample_rate),
    }
    client = presence_transport or UrllibPresenceAudioPushTransport()
    try:
        status, payload = client.post_pcm(
            url=presence_push.url,
            headers=headers,
            body=bytes(pcm),
            timeout_s=presence_push.timeout_s,
        )
    except Exception as exc:
        state = _reconcile_ambiguous_push(
            ticket_path=ticket_path,
            ticket_id=ticket.ticket_id,
            now=current,
            error_code=f"presence_push_transport:{type(exc).__name__}",
        )
        return ApprovedAvatarTurnExecution(
            meeting_id=ticket.meeting_id,
            avatar_id=ticket.avatar_id,
            ticket_id=ticket.ticket_id,
            audio_sha256=ticket.audio_sha256,
            pcm_bytes=ticket.pcm_bytes,
            sample_rate=ticket.sample_rate,
            state=state,
            browser_playback_completed=(state == "completed"),
            speech_transmission_performed=(state == "completed"),
        )

    current_record = _record(ticket_path)
    record_state = str(current_record.get("state") or "")
    if status != 200:
        if record_state == "in_flight":
            record_state = _reconcile_ambiguous_push(
                ticket_path=ticket_path,
                ticket_id=ticket.ticket_id,
                now=current,
                error_code=f"presence_push_http_{status}",
            )
        return ApprovedAvatarTurnExecution(
            meeting_id=ticket.meeting_id,
            avatar_id=ticket.avatar_id,
            ticket_id=ticket.ticket_id,
            audio_sha256=ticket.audio_sha256,
            pcm_bytes=ticket.pcm_bytes,
            sample_rate=ticket.sample_rate,
            state=record_state or "reconciliation_required",
            browser_playback_completed=False,
            speech_transmission_performed=False,
        )

    if str(payload.get("ticket_id") or "") != ticket.ticket_id:
        raise RuntimeError("Presence response ticket identity mismatch")
    if str(payload.get("audio_sha256") or "") != ticket.audio_sha256:
        raise RuntimeError("Presence response audio identity mismatch")
    if payload.get("browser_playback_completed") is not True:
        raise RuntimeError("Presence browser playback completion missing")
    if payload.get("speech_transmission_performed") is not True:
        raise RuntimeError("Presence speech transmission evidence missing")
    if payload.get("meeting_audio_delivery_verified") is not False:
        raise RuntimeError("Presence response overclaims meeting delivery")
    if record_state != "completed":
        raise RuntimeError("speech transmission ticket not completed")

    return ApprovedAvatarTurnExecution(
        meeting_id=ticket.meeting_id,
        avatar_id=ticket.avatar_id,
        ticket_id=ticket.ticket_id,
        audio_sha256=ticket.audio_sha256,
        pcm_bytes=ticket.pcm_bytes,
        sample_rate=ticket.sample_rate,
        state="completed",
        browser_playback_completed=True,
        speech_transmission_performed=True,
    )
