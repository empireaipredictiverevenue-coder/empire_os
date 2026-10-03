"""Authenticated browser Presence surface for Recall Output Media.

The public page is intentionally inert: no microphone, no AudioContext, no
media autoplay and no speech path. It establishes a short-lived, cookie-bound
Presence session and a websocket control channel for future governed renderers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import secrets
import threading
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

from empire_os.digital_avatar_presence_audio import (
    PresenceAudioBroker,
    PresenceAudioCommand,
)
from empire_os.digital_avatar_presence_token import (
    AvatarPresenceClaims,
    verify_avatar_presence_token,
)
from empire_os.digital_avatar_presence_transcript import (
    PresenceTranscriptObservation,
    normalize_presence_transcript,
)


_COOKIE = "empire_avatar_presence"
_PROTOCOL = "empire.avatar.presence.v1"


@dataclass(frozen=True)
class PresenceBrowserSession:
    session_id: str
    claims: AvatarPresenceClaims
    created_at: int
    audio_locked: bool = True
    visual_attached: bool = False
    speech_transmission_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "none"

    def public_state(self) -> dict[str, Any]:
        return {
            "protocol": _PROTOCOL,
            "meeting_id": self.claims.meeting_id,
            "avatar_id": self.claims.avatar_id,
            "bot_id": self.claims.bot_id,
            "mode": self.claims.mode,
            "audio_locked": self.audio_locked,
            "visual_attached": self.visual_attached,
            "speech_transmission_allowed": self.speech_transmission_allowed,
            "commercial_execution_allowed": self.commercial_execution_allowed,
            "execution_authority": self.execution_authority,
        }


class PresenceBrowserRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, PresenceBrowserSession] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        claims: AvatarPresenceClaims,
        now: datetime,
    ) -> PresenceBrowserSession:
        session = PresenceBrowserSession(
            session_id=secrets.token_urlsafe(24),
            claims=claims,
            created_at=int(now.astimezone(timezone.utc).timestamp()),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(
        self,
        *,
        session_id: str | None,
        now: datetime,
    ) -> PresenceBrowserSession | None:
        clean = str(session_id or "").strip()
        if not clean:
            return None
        current = int(now.astimezone(timezone.utc).timestamp())
        with self._lock:
            session = self._sessions.get(clean)
            if session is None:
                return None
            if current >= session.claims.expires_at:
                self._sessions.pop(clean, None)
                return None
            return session

    def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(str(session_id or ""), None
            )


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI Digital Avatar Presence</title>
<link rel="stylesheet" href="/avatar/presence/runtime.css">
</head>
<body>
<main id="presence" aria-live="polite">
  <div class="mark">EMPIRE AI</div>
  <div id="status">Digital Avatar Presence starting…</div>
</main>
<script src="/avatar/presence/runtime.js" defer></script>
</body>
</html>
"""

_JS = r"""(() => {
  history.replaceState({}, document.title, location.pathname);
  const status = document.getElementById("status");
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${scheme}//${location.host}/avatar/presence/ws`);
  const pendingAudio = new Map();

  function send(message) {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }

  function failPlayback(ticketId, audioSha256, error) {
    send({
      type: "speech.playback.failed",
      ticket_id: ticketId,
      audio_sha256: audioSha256,
      error: String(error || "playback_failed").slice(0, 240)
    });
  }

  function decodeBase64(value) {
    const raw = atob(String(value || ""));
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) {
      bytes[i] = raw.charCodeAt(i);
    }
    return bytes;
  }

  async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
  }

  async function playApprovedPcm(state) {
    const total = state.chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    if (total !== state.pcm_bytes) {
      throw new Error("pcm_size_mismatch");
    }
    const pcm = new Uint8Array(total);
    let offset = 0;
    for (const chunk of state.chunks) {
      pcm.set(chunk, offset);
      offset += chunk.length;
    }
    const digest = await sha256Hex(pcm.buffer);
    if (digest !== state.audio_sha256) {
      throw new Error("pcm_sha256_mismatch");
    }
    if (pcm.length % 2 !== 0) {
      throw new Error("pcm_alignment_invalid");
    }

    const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error("audio_context_unavailable");
    }
    const context = new AudioContextClass({sampleRate: state.sample_rate});
    try {
      if (context.state === "suspended") {
        await context.resume();
      }
      const samples = pcm.length / 2;
      const buffer = context.createBuffer(1, samples, state.sample_rate);
      const channel = buffer.getChannelData(0);
      const view = new DataView(pcm.buffer, pcm.byteOffset, pcm.byteLength);
      for (let i = 0; i < samples; i += 1) {
        channel[i] = view.getInt16(i * 2, true) / 32768;
      }
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      send({
        type: "speech.playback.started",
        ticket_id: state.ticket_id,
        audio_sha256: state.audio_sha256
      });
      await new Promise((resolve, reject) => {
        source.onended = resolve;
        try {
          source.start(0);
        } catch (error) {
          reject(error);
        }
      });
      send({
        type: "speech.playback.completed",
        ticket_id: state.ticket_id,
        audio_sha256: state.audio_sha256
      });
    } finally {
      try { await context.close(); } catch (_) {}
    }
  }

  async function handleServerMessage(data) {
    if (data.type === "presence.ready") {
      status.textContent = data.visual_attached
        ? "Digital Avatar Presence ready"
        : "Digital Avatar visual renderer not attached";
      document.body.dataset.audioLocked = String(data.audio_locked);
      return;
    }

    if (data.type === "speech.audio.begin") {
      if (
        !data.ticket_id
        || !data.audio_sha256
        || data.encoding !== "pcm_s16le"
        || !Number.isInteger(data.sample_rate)
        || !Number.isInteger(data.pcm_bytes)
        || !Number.isInteger(data.chunk_count)
        || data.sample_rate < 8000
        || data.sample_rate > 48000
        || data.pcm_bytes <= 0
        || data.chunk_count <= 0
        || pendingAudio.has(data.ticket_id)
      ) {
        failPlayback(data.ticket_id, data.audio_sha256, "audio_begin_invalid");
        return;
      }
      pendingAudio.set(data.ticket_id, {
        ticket_id: data.ticket_id,
        audio_sha256: data.audio_sha256,
        sample_rate: data.sample_rate,
        pcm_bytes: data.pcm_bytes,
        chunk_count: data.chunk_count,
        chunks: []
      });
      return;
    }

    if (data.type === "speech.audio.chunk") {
      const state = pendingAudio.get(data.ticket_id);
      if (
        !state
        || data.index !== state.chunks.length
        || state.chunks.length >= state.chunk_count
      ) {
        failPlayback(data.ticket_id, state?.audio_sha256 || "", "audio_chunk_invalid");
        pendingAudio.delete(data.ticket_id);
        return;
      }
      try {
        state.chunks.push(decodeBase64(data.b64));
      } catch (_) {
        failPlayback(data.ticket_id, state.audio_sha256, "audio_chunk_decode_failed");
        pendingAudio.delete(data.ticket_id);
      }
      return;
    }

    if (data.type === "speech.audio.end") {
      const state = pendingAudio.get(data.ticket_id);
      pendingAudio.delete(data.ticket_id);
      if (
        !state
        || state.audio_sha256 !== data.audio_sha256
        || state.chunks.length !== state.chunk_count
      ) {
        failPlayback(data.ticket_id, data.audio_sha256, "audio_end_invalid");
        return;
      }
      try {
        await playApprovedPcm(state);
      } catch (error) {
        failPlayback(state.ticket_id, state.audio_sha256, error);
      }
    }
  }

  socket.addEventListener("open", () => {
    send({type:"hello", protocol:"empire.avatar.presence.v1"});
  });
  socket.addEventListener("message", (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (_) { return; }
    void handleServerMessage(data);
  });
  socket.addEventListener("close", () => {
    status.textContent = "Digital Avatar Presence disconnected";
    pendingAudio.clear();
  });

  const recallTranscript = new WebSocket(
    "wss://meeting-data.bot.recall.ai/api/v1/transcript"
  );
  recallTranscript.addEventListener("message", (event) => {
    let payload;
    try { payload = JSON.parse(event.data); } catch (_) { return; }
    send({
      type: "recall.transcript.observed",
      payload
    });
  });
})();
"""

_CSS = """html,body{margin:0;width:100%;height:100%;background:#050b18;color:#eaf2ff;
font-family:Inter,system-ui,sans-serif}body{display:grid;place-items:center}
#presence{text-align:center}.mark{font-weight:800;letter-spacing:.28em;font-size:2rem}
#status{margin-top:1rem;opacity:.72;font-size:1rem}"""


def _security_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self' ws: wss:; img-src 'self' data:; "
            "media-src 'self' blob:; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'self'"
        ),
    }


def create_digital_avatar_presence_app(
    *,
    secret_provider: Callable[[], str],
    registry: PresenceBrowserRegistry | None = None,
    now_provider: Callable[[], datetime] | None = None,
    transcript_sink: Callable[[PresenceTranscriptObservation], Any] | None = None,
    audio_push_secret_provider: Callable[[], str] | None = None,
    speech_ticket_validator: Callable[..., Any] | None = None,
    speech_ticket_finalizer: Callable[..., Any] | None = None,
    audio_broker: PresenceAudioBroker | None = None,
    max_audio_bytes: int = 12_000_000,
    audio_push_timeout_s: float = 90.0,
) -> FastAPI:
    sessions = registry or PresenceBrowserRegistry()
    clock = now_provider or (lambda: datetime.now(timezone.utc))
    broker = audio_broker or PresenceAudioBroker(
        max_audio_bytes=max_audio_bytes,
    )
    app = FastAPI(
        title="Empire Digital Avatar Presence",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/avatar/presence", response_class=HTMLResponse)
    def presence(request: Request, token: str | None = None):
        now = clock()
        session = sessions.get(
            session_id=request.cookies.get(_COOKIE),
            now=now,
        )
        if session is None:
            raw_token = str(token or "").strip()
            if not raw_token:
                raise HTTPException(
                    status_code=401,
                    detail="presence_token_required",
                )
            try:
                claims = verify_avatar_presence_token(
                    secret=secret_provider(),
                    token=raw_token,
                    now=now,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=401,
                    detail="presence_token_invalid",
                ) from exc
            session = sessions.create(claims=claims, now=now)

        response = HTMLResponse(_HTML, headers=_security_headers())
        max_age = max(
            0,
            session.claims.expires_at
            - int(now.astimezone(timezone.utc).timestamp()),
        )
        response.set_cookie(
            _COOKIE,
            session.session_id,
            max_age=max_age,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/avatar/presence",
        )
        return response

    @app.get("/avatar/presence/runtime.js")
    def runtime_js():
        return Response(
            _JS,
            media_type="application/javascript",
            headers=_security_headers(),
        )

    @app.get("/avatar/presence/runtime.css")
    def runtime_css():
        return Response(
            _CSS,
            media_type="text/css",
            headers=_security_headers(),
        )

    @app.post("/internal/avatar/presence/audio")
    async def internal_presence_audio(request: Request):
        if (
            audio_push_secret_provider is None
            or speech_ticket_validator is None
            or speech_ticket_finalizer is None
        ):
            raise HTTPException(
                status_code=503,
                detail="presence_audio_push_not_configured",
            )
        secret = str(audio_push_secret_provider() or "").strip()
        if len(secret.encode("utf-8")) < 32:
            raise HTTPException(
                status_code=503,
                detail="presence_audio_push_secret_unavailable",
            )
        supplied = str(request.headers.get("authorization") or "")
        expected = "Bearer " + secret
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=401,
                detail="presence_audio_push_unauthorized",
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_audio_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="presence_audio_payload_too_large",
                    )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="presence_audio_content_length_invalid",
                ) from exc

        raw = await request.body()
        if not raw:
            raise HTTPException(
                status_code=400,
                detail="presence_audio_pcm_required",
            )
        if len(raw) > max_audio_bytes:
            raise HTTPException(
                status_code=413,
                detail="presence_audio_payload_too_large",
            )

        ticket_id = str(
            request.headers.get("x-empire-ticket-id") or ""
        ).strip()
        meeting_id = str(
            request.headers.get("x-empire-meeting-id") or ""
        ).strip()
        avatar_id = str(
            request.headers.get("x-empire-avatar-id") or ""
        ).strip()
        bot_id = str(
            request.headers.get("x-empire-bot-id") or ""
        ).strip()
        audio_sha256 = str(
            request.headers.get("x-empire-audio-sha256") or ""
        ).strip().lower()
        try:
            sample_rate = int(
                request.headers.get("x-empire-sample-rate") or "0"
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="presence_audio_sample_rate_invalid",
            ) from exc

        actual_sha256 = sha256(raw).hexdigest()
        if not hmac.compare_digest(audio_sha256, actual_sha256):
            raise HTTPException(
                status_code=409,
                detail="presence_audio_sha256_mismatch",
            )

        try:
            speech_ticket_validator(
                ticket_id=ticket_id,
                meeting_id=meeting_id,
                avatar_id=avatar_id,
                bot_id=bot_id,
                audio_sha256=audio_sha256,
                pcm_bytes=len(raw),
                sample_rate=sample_rate,
                now=clock(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        command = PresenceAudioCommand(
            ticket_id=ticket_id,
            meeting_id=meeting_id,
            avatar_id=avatar_id,
            bot_id=bot_id,
            audio_sha256=audio_sha256,
            sample_rate=sample_rate,
            pcm=raw,
        )
        try:
            result = await broker.push_pcm(
                command,
                timeout_s=audio_push_timeout_s,
            )
        except TimeoutError as exc:
            try:
                speech_ticket_finalizer(
                    ticket_id=ticket_id,
                    performed=False,
                    now=clock(),
                    error_code="presence_audio_playback_timeout",
                )
            except Exception as finalize_exc:
                raise HTTPException(
                    status_code=503,
                    detail="presence_audio_reconciliation_finalize_failed",
                ) from finalize_exc
            raise HTTPException(
                status_code=504,
                detail="presence_audio_playback_timeout",
            ) from exc
        except (ValueError, RuntimeError) as exc:
            try:
                speech_ticket_finalizer(
                    ticket_id=ticket_id,
                    performed=False,
                    now=clock(),
                    error_code=f"presence_audio_delivery_error:{type(exc).__name__}",
                )
            except Exception as finalize_exc:
                raise HTTPException(
                    status_code=503,
                    detail="presence_audio_reconciliation_finalize_failed",
                ) from finalize_exc
            status_code = 409 if isinstance(exc, ValueError) else 503
            raise HTTPException(
                status_code=status_code,
                detail=str(exc),
            ) from exc

        try:
            finalized = speech_ticket_finalizer(
                ticket_id=ticket_id,
                performed=True,
                now=clock(),
                error_code=None,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="presence_audio_success_finalize_failed",
            ) from exc

        return {
            **result.as_dict(),
            "speech_transmission_performed": True,
            "meeting_audio_delivery_verified": False,
            "browser_playback_completed": True,
            "ticket_state": (
                finalized.get("state")
                if isinstance(finalized, dict)
                else "completed"
            ),
            "raw_audio_persisted": False,
        }


    @app.websocket("/avatar/presence/ws")
    async def presence_ws(websocket: WebSocket):
        now = clock()
        session = sessions.get(
            session_id=websocket.cookies.get(_COOKIE),
            now=now,
        )
        if session is None:
            await websocket.close(
                code=4401,
                reason="presence_session_invalid",
            )
            return

        await websocket.accept()
        try:
            first = await websocket.receive_json()
            if not isinstance(first, dict):
                await websocket.close(
                    code=4400,
                    reason="presence_protocol_invalid",
                )
                return
            if (
                first.get("type") != "hello"
                or first.get("protocol") != _PROTOCOL
            ):
                await websocket.close(
                    code=4400,
                    reason="presence_protocol_invalid",
                )
                return

            try:
                broker.attach(
                    session_id=session.session_id,
                    claims=session.claims,
                    socket=websocket,
                )
            except ValueError:
                await websocket.close(
                    code=4409,
                    reason="presence_session_already_attached",
                )
                return

            await websocket.send_json({
                "type": "presence.ready",
                **session.public_state(),
            })

            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "protocol": _PROTOCOL,
                        "execution_authority": "none",
                    })
                    continue

                if broker.acknowledge(
                    session_id=session.session_id,
                    message=message,
                ):
                    continue

                if message.get("type") == "recall.transcript.observed":
                    payload = message.get("payload")
                    try:
                        observation = normalize_presence_transcript(
                            claims=session.claims,
                            payload=payload,
                            received_at=clock().isoformat(),
                        )
                    except ValueError:
                        await websocket.send_json({
                            "type": "error",
                            "code": "transcript_observation_invalid",
                            "execution_authority": "none",
                        })
                        continue
                    if transcript_sink is not None:
                        try:
                            transcript_sink(observation)
                        except Exception:
                            await websocket.send_json({
                                "type": "error",
                                "code": "transcript_sink_unavailable",
                                "execution_authority": "none",
                            })
                            continue
                    await websocket.send_json({
                        "type": "transcript.accepted",
                        "observation_id": observation.observation_id,
                        "truth_class": observation.truth_class,
                        "canonical_evidence": False,
                        "commercial_truth_allowed": False,
                        "execution_authority": "none",
                    })
                    continue

                await websocket.send_json({
                    "type": "error",
                    "code": "client_command_not_allowed",
                    "execution_authority": "none",
                })
        except WebSocketDisconnect:
            return
        finally:
            broker.detach(session_id=session.session_id)

    return app
