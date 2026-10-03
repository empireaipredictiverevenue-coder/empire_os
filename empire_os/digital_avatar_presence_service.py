"""Loopback service for authenticated Digital Avatar Presence browser runtime."""
from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from empire_os.digital_avatar_presence_api import (
    PresenceBrowserRegistry,
    create_digital_avatar_presence_app,
)
from empire_os.digital_avatar_presence_spool import FilePresenceTranscriptSpool
from empire_os.digital_avatar_speech_transmission import (
    finalize_inflight_speech_transmission_record,
    validate_inflight_speech_transmission_record,
)


DEFAULT_FAST_SPOOL_ROOT = Path(
    os.getenv(
        "EMPIRE_AVATAR_PRESENCE_FAST_SPOOL",
        "/srv/empire_os/runtime/digital_avatar/presence_fast_transcripts",
    )
)
DEFAULT_SPEECH_TICKET_ROOT = Path(
    os.getenv(
        "EMPIRE_AVATAR_SPEECH_TICKET_ROOT",
        "/srv/empire_os/runtime/digital_avatar/speech_tickets",
    )
)
_TICKET_ID_RE = re.compile(r"^avatar-speech:[0-9a-f]{64}$")


def _env_secret() -> str:
    return os.getenv(
        "EMPIRE_AVATAR_PRESENCE_SIGNING_SECRET",
        "",
    ).strip()


def _env_audio_push_secret() -> str:
    return os.getenv(
        "EMPIRE_AVATAR_PRESENCE_AUDIO_PUSH_SECRET",
        "",
    ).strip()


def _speech_ticket_path(
    *,
    root: str | Path,
    ticket_id: str,
) -> Path:
    clean = str(ticket_id or "").strip().lower()
    if not _TICKET_ID_RE.fullmatch(clean):
        raise ValueError("speech transmission ticket id invalid")
    return Path(root) / f"{clean.replace(':', '__')}.json"


def create_presence_service_app(
    *,
    secret_provider: Callable[[], str],
    spool: FilePresenceTranscriptSpool,
    registry: PresenceBrowserRegistry | None = None,
    audio_push_secret_provider: Callable[[], str] | None = None,
    speech_ticket_root: str | Path = DEFAULT_SPEECH_TICKET_ROOT,
) -> FastAPI:
    push_secret_provider = audio_push_secret_provider or (lambda: "")

    def validate_ticket(**kwargs):
        ticket_id = str(kwargs.pop("ticket_id"))
        return validate_inflight_speech_transmission_record(
            path=_speech_ticket_path(
                root=speech_ticket_root,
                ticket_id=ticket_id,
            ),
            ticket_id=ticket_id,
            **kwargs,
        )

    def finalize_ticket(**kwargs):
        ticket_id = str(kwargs.pop("ticket_id"))
        return finalize_inflight_speech_transmission_record(
            path=_speech_ticket_path(
                root=speech_ticket_root,
                ticket_id=ticket_id,
            ),
            ticket_id=ticket_id,
            **kwargs,
        )

    app = create_digital_avatar_presence_app(
        secret_provider=secret_provider,
        registry=registry,
        transcript_sink=spool.enqueue,
        audio_push_secret_provider=push_secret_provider,
        speech_ticket_validator=validate_ticket,
        speech_ticket_finalizer=finalize_ticket,
    )

    @app.get("/health")
    def health():
        secret = str(secret_provider() or "")
        configured = len(secret.encode("utf-8")) >= 32
        push_secret = str(push_secret_provider() or "")
        audio_push_configured = len(push_secret.encode("utf-8")) >= 32
        return JSONResponse(
            {
                "ok": configured,
                "mode": "COPILOT_PREPARED",
                "service": "empire-digital-avatar-presence",
                "presence_signing_configured": configured,
                "approved_turn_audio_configured": audio_push_configured,
                "approved_turn_audio_ready": (
                    configured and audio_push_configured
                ),
                "speech_ticket_root": str(speech_ticket_root),
                "fast_transcript_truth_class": "SESSION_OBSERVED",
                "canonical_truth_written": False,
                "speech_execution": False,
                "autonomous_speech_execution": False,
                "commercial_execution": False,
                "execution_authority": "none",
            },
            status_code=200 if configured else 503,
        )
    return app


SPOOL = FilePresenceTranscriptSpool(DEFAULT_FAST_SPOOL_ROOT)
app = create_presence_service_app(
    secret_provider=_env_secret,
    audio_push_secret_provider=_env_audio_push_secret,
    speech_ticket_root=DEFAULT_SPEECH_TICKET_ROOT,
    spool=SPOOL,
)
