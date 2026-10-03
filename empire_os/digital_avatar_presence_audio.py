"""One-turn server-to-browser PCM broker for Digital Avatar Presence."""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from hashlib import sha256
import re
import threading
from typing import Any, Mapping, Protocol

from empire_os.digital_avatar_presence_token import AvatarPresenceClaims


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PresenceAudioSocket(Protocol):
    async def send_json(self, data: Any) -> None:
        ...


@dataclass(frozen=True)
class PresenceAudioCommand:
    ticket_id: str
    meeting_id: str
    avatar_id: str
    bot_id: str
    audio_sha256: str
    sample_rate: int
    pcm: bytes
    encoding: str = "pcm_s16le"

    @property
    def pcm_bytes(self) -> int:
        return len(self.pcm)

    def validate(self, *, max_audio_bytes: int) -> None:
        for label, value in (
            ("ticket_id", self.ticket_id),
            ("meeting_id", self.meeting_id),
            ("avatar_id", self.avatar_id),
            ("bot_id", self.bot_id),
        ):
            if not str(value or "").strip():
                raise ValueError(f"presence audio {label} required")
        if not _SHA256_RE.fullmatch(str(self.audio_sha256 or "").lower()):
            raise ValueError("presence audio sha256 invalid")
        if self.encoding != "pcm_s16le":
            raise ValueError("presence audio encoding unsupported")
        if self.sample_rate < 8000 or self.sample_rate > 48000:
            raise ValueError("presence audio sample rate unsupported")
        if self.pcm_bytes <= 0:
            raise ValueError("presence audio PCM required")
        if self.pcm_bytes > int(max_audio_bytes):
            raise ValueError("presence audio exceeds configured limit")
        if self.pcm_bytes % 2:
            raise ValueError("presence audio PCM must contain int16 samples")
        if sha256(self.pcm).hexdigest() != str(self.audio_sha256).lower():
            raise ValueError("presence audio sha256 mismatch")


@dataclass(frozen=True)
class PresenceAudioPlaybackResult:
    ticket_id: str
    meeting_id: str
    avatar_id: str
    bot_id: str
    audio_sha256: str
    pcm_bytes: int
    sample_rate: int
    playback_completed: bool
    browser_acknowledged: bool = True
    commercial_execution_allowed: bool = False
    execution_authority: str = "approved_turn_audio_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "meeting_id": self.meeting_id,
            "avatar_id": self.avatar_id,
            "bot_id": self.bot_id,
            "audio_sha256": self.audio_sha256,
            "pcm_bytes": self.pcm_bytes,
            "sample_rate": self.sample_rate,
            "playback_completed": self.playback_completed,
            "browser_acknowledged": self.browser_acknowledged,
            "commercial_execution_allowed": self.commercial_execution_allowed,
            "execution_authority": self.execution_authority,
        }


@dataclass
class _Connection:
    session_id: str
    claims: AvatarPresenceClaims
    socket: PresenceAudioSocket


@dataclass
class _Pending:
    session_id: str
    audio_sha256: str
    future: asyncio.Future


class PresenceAudioBroker:
    def __init__(
        self,
        *,
        max_audio_bytes: int = 12_000_000,
        chunk_bytes: int = 32_768,
    ) -> None:
        if max_audio_bytes <= 0:
            raise ValueError("presence max audio bytes must be positive")
        if chunk_bytes < 1024 or chunk_bytes > 131_072:
            raise ValueError("presence audio chunk size invalid")
        self.max_audio_bytes = int(max_audio_bytes)
        self.chunk_bytes = int(chunk_bytes)
        self._connections: dict[str, _Connection] = {}
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()

    def attach(
        self,
        *,
        session_id: str,
        claims: AvatarPresenceClaims,
        socket: PresenceAudioSocket,
    ) -> None:
        clean = str(session_id or "").strip()
        if not clean:
            raise ValueError("presence browser session id required")
        with self._lock:
            existing = self._connections.get(clean)
            if existing is not None and existing.socket is not socket:
                raise ValueError("presence browser session already attached")
            self._connections[clean] = _Connection(
                session_id=clean,
                claims=claims,
                socket=socket,
            )

    def detach(self, *, session_id: str) -> None:
        clean = str(session_id or "").strip()
        pending: list[asyncio.Future] = []
        with self._lock:
            self._connections.pop(clean, None)
            for ticket_id, value in list(self._pending.items()):
                if value.session_id == clean:
                    pending.append(value.future)
                    self._pending.pop(ticket_id, None)
        for future in pending:
            if not future.done():
                future.set_exception(
                    RuntimeError("presence browser disconnected")
                )

    def _connection_for(
        self,
        *,
        meeting_id: str,
        avatar_id: str,
        bot_id: str,
    ) -> _Connection:
        with self._lock:
            matches = [
                value
                for value in self._connections.values()
                if value.claims.meeting_id == meeting_id
                and value.claims.avatar_id == avatar_id
                and value.claims.bot_id == bot_id
                and value.claims.mode == "copilot"
            ]
        if not matches:
            raise ValueError("presence browser is not connected")
        if len(matches) != 1:
            raise ValueError("presence browser connection is ambiguous")
        return matches[0]

    async def push_pcm(
        self,
        command: PresenceAudioCommand,
        *,
        timeout_s: float,
    ) -> PresenceAudioPlaybackResult:
        command.validate(max_audio_bytes=self.max_audio_bytes)
        if timeout_s <= 0 or timeout_s > 180:
            raise ValueError("presence playback timeout invalid")
        connection = self._connection_for(
            meeting_id=command.meeting_id,
            avatar_id=command.avatar_id,
            bot_id=command.bot_id,
        )
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        with self._lock:
            if command.ticket_id in self._pending:
                raise ValueError("presence audio ticket already pending")
            self._pending[command.ticket_id] = _Pending(
                session_id=connection.session_id,
                audio_sha256=command.audio_sha256,
                future=future,
            )

        chunks = [
            command.pcm[offset: offset + self.chunk_bytes]
            for offset in range(0, command.pcm_bytes, self.chunk_bytes)
        ]
        try:
            await connection.socket.send_json({
                "type": "speech.audio.begin",
                "ticket_id": command.ticket_id,
                "audio_sha256": command.audio_sha256,
                "encoding": command.encoding,
                "sample_rate": command.sample_rate,
                "pcm_bytes": command.pcm_bytes,
                "chunk_count": len(chunks),
            })
            for index, chunk in enumerate(chunks):
                await connection.socket.send_json({
                    "type": "speech.audio.chunk",
                    "ticket_id": command.ticket_id,
                    "index": index,
                    "b64": base64.b64encode(chunk).decode("ascii"),
                })
            await connection.socket.send_json({
                "type": "speech.audio.end",
                "ticket_id": command.ticket_id,
                "audio_sha256": command.audio_sha256,
            })
            result = await asyncio.wait_for(future, timeout=timeout_s)
            if result is not True:
                raise RuntimeError("presence browser playback failed")
            return PresenceAudioPlaybackResult(
                ticket_id=command.ticket_id,
                meeting_id=command.meeting_id,
                avatar_id=command.avatar_id,
                bot_id=command.bot_id,
                audio_sha256=command.audio_sha256,
                pcm_bytes=command.pcm_bytes,
                sample_rate=command.sample_rate,
                playback_completed=True,
            )
        finally:
            with self._lock:
                current = self._pending.get(command.ticket_id)
                if current is not None and current.future is future:
                    self._pending.pop(command.ticket_id, None)

    def acknowledge(
        self,
        *,
        session_id: str,
        message: Mapping[str, Any],
    ) -> bool:
        kind = str(message.get("type") or "").strip()
        if kind not in {
            "speech.playback.started",
            "speech.playback.completed",
            "speech.playback.failed",
        }:
            return False
        ticket_id = str(message.get("ticket_id") or "").strip()
        audio_sha256 = str(message.get("audio_sha256") or "").strip()
        if not ticket_id or not audio_sha256:
            return False

        with self._lock:
            pending = self._pending.get(ticket_id)
        if pending is None or pending.session_id != str(session_id or "").strip():
            return False
        if pending.audio_sha256 != audio_sha256:
            return False

        if kind == "speech.playback.started":
            return True
        if pending.future.done():
            return False
        if kind == "speech.playback.completed":
            pending.future.set_result(True)
        else:
            pending.future.set_exception(
                RuntimeError(
                    str(message.get("error") or "presence playback failed")
                )
            )
        return True
