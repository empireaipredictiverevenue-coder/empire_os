"""Authenticated GPU voice-render sidecar contract for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Iterator, Mapping, Protocol
from urllib.parse import urlparse
import urllib.request

from empire_os.digital_avatar_speech import AvatarSpeechRenderTask
from empire_os.digital_avatar_voice_profile import AvatarVoiceRenderPlan


@dataclass(frozen=True)
class AvatarVoiceSidecarConfig:
    base_url: str
    auth_token: str
    timeout_s: float = 20.0
    max_audio_bytes: int = 12_000_000
    allow_loopback_http: bool = False

    def validate(self) -> None:
        parsed = urlparse(str(self.base_url or "").strip())
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("voice sidecar URL invalid")
        host = (parsed.hostname or "").lower()
        loopback = host in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https":
            if not (
                self.allow_loopback_http
                and loopback
                and parsed.scheme == "http"
            ):
                raise ValueError("voice sidecar must use HTTPS")
        if not str(self.auth_token or "").strip():
            raise ValueError("voice sidecar auth token required")
        if self.timeout_s <= 0:
            raise ValueError("voice sidecar timeout must be positive")
        if self.max_audio_bytes <= 0:
            raise ValueError("voice sidecar max audio bytes must be positive")


@dataclass(frozen=True)
class AvatarVoiceSidecarRequest:
    render_id: str
    engine: str
    model_ref: str
    voice_id: str
    text: str
    text_sha256: str
    language: str
    output_format: str = "pcm_s16le"
    sample_rate: int = 24000
    stream: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AvatarVoiceRenderArtifact:
    render_id: str
    engine: str
    voice_id: str
    text_sha256: str
    audio_sha256: str
    pcm_bytes: int
    sample_rate: int
    chunk_count: int
    local_render_performed: bool = True
    meeting_transmission_performed: bool = False
    speech_execution_performed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class VoiceSidecarStreamTransport(Protocol):
    def stream(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Iterator[bytes]]:
        ...


class UrllibVoiceSidecarTransport:
    def stream(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Iterator[bytes]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        response = urllib.request.urlopen(request, timeout=timeout_s)

        def chunks() -> Iterator[bytes]:
            try:
                while True:
                    chunk = response.read(32_768)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()

        return response.status, dict(response.headers), chunks()


def _render_id(
    *,
    task: AvatarSpeechRenderTask,
    plan: AvatarVoiceRenderPlan,
) -> str:
    material = "|".join(
        (
            task.meeting_id,
            task.avatar_id,
            task.text_sha256,
            plan.engine,
            plan.engine_voice_id,
        )
    ).encode("utf-8")
    return "avatar-voice:" + sha256(material).hexdigest()


def build_voice_sidecar_request(
    *,
    task: AvatarSpeechRenderTask,
    plan: AvatarVoiceRenderPlan,
) -> AvatarVoiceSidecarRequest:
    if task.meeting_id != plan.meeting_id:
        raise ValueError("voice task/plan meeting mismatch")
    if task.avatar_id != plan.avatar_id:
        raise ValueError("voice task/plan avatar mismatch")
    if task.voice_profile_ref != plan.voice_profile_ref:
        raise ValueError("voice task/plan profile mismatch")
    if task.meeting_transmission_allowed:
        raise ValueError("voice task must not allow meeting transmission")
    if plan.meeting_transmission_allowed:
        raise ValueError("voice plan must not allow meeting transmission")
    if not plan.local_audio_render_allowed:
        raise ValueError("voice plan does not allow local render")
    if not str(plan.engine_voice_id or "").strip():
        raise ValueError("registered sidecar voice id required")
    if not str(plan.model_ref or "").strip():
        raise ValueError("voice model ref required")

    return AvatarVoiceSidecarRequest(
        render_id=_render_id(task=task, plan=plan),
        engine=plan.engine,
        model_ref=str(plan.model_ref),
        voice_id=plan.engine_voice_id,
        text=task.text,
        text_sha256=task.text_sha256,
        language=plan.language,
    )


def render_voice_sidecar_pcm(
    *,
    config: AvatarVoiceSidecarConfig,
    request: AvatarVoiceSidecarRequest,
    on_chunk: Callable[[bytes], None],
    transport: VoiceSidecarStreamTransport | None = None,
) -> AvatarVoiceRenderArtifact:
    config.validate()
    client = transport or UrllibVoiceSidecarTransport()
    endpoint = config.base_url.rstrip("/") + "/v1/render"
    status, headers, stream = client.stream(
        url=endpoint,
        headers={
            "Authorization": "Bearer " + config.auth_token,
            "Content-Type": "application/json",
            "Accept": "audio/L16",
            "X-Empire-Render-Id": request.render_id,
        },
        payload=request.as_dict(),
        timeout_s=config.timeout_s,
    )
    if status != 200:
        raise RuntimeError(
            f"voice sidecar render failed with status {status}"
        )

    content_type = str(
        headers.get("content-type")
        or headers.get("Content-Type")
        or ""
    ).lower()
    if "audio/" not in content_type:
        raise RuntimeError("voice sidecar returned non-audio content")

    digest = sha256()
    total = 0
    chunks = 0
    for chunk in stream:
        if not isinstance(chunk, (bytes, bytearray)):
            raise RuntimeError("voice sidecar returned invalid audio chunk")
        value = bytes(chunk)
        if not value:
            continue
        total += len(value)
        if total > config.max_audio_bytes:
            raise RuntimeError("voice sidecar audio exceeds configured limit")
        digest.update(value)
        on_chunk(value)
        chunks += 1

    if total == 0:
        raise RuntimeError("voice sidecar returned empty audio")

    return AvatarVoiceRenderArtifact(
        render_id=request.render_id,
        engine=request.engine,
        voice_id=request.voice_id,
        text_sha256=request.text_sha256,
        audio_sha256=digest.hexdigest(),
        pcm_bytes=total,
        sample_rate=request.sample_rate,
        chunk_count=chunks,
    )
