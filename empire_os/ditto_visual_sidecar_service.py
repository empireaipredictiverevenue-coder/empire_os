"""Authenticated realtime visual-render sidecar boundary for Digital Avatar.

The service is transport/render-only. It owns no meeting, speech, commercial,
payment or revenue authority. A concrete Ditto engine is injected on the GPU
host through EMPIRE_DITTO_ENGINE_FACTORY.
"""
from __future__ import annotations

import base64
import hmac
from hashlib import sha256
import importlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Mapping, Protocol

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


_AVATAR_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BOUNDARY = "empireframe"


class RealtimeVisualEngine(Protocol):
    @property
    def engine_name(self) -> str:
        ...

    @property
    def model_ref(self) -> str:
        ...

    def avatar_exists(self, avatar_id: str) -> bool:
        ...

    def register_avatar(
        self,
        *,
        avatar_id: str,
        source_image_path: str,
    ) -> None:
        ...

    def stream_jpeg_frames(
        self,
        *,
        avatar_id: str,
        pcm: bytes,
        sample_rate: int,
        target_fps: int,
    ) -> Iterable[bytes]:
        ...


class VisualRegisterRequest(BaseModel):
    avatar_id: str
    source_image_base64: str
    consent_evidence_ref: str = Field(min_length=1, max_length=512)


def _authorized(token: str, supplied: str | None) -> None:
    expected = "Bearer " + token
    if not hmac.compare_digest(str(supplied or ""), expected):
        raise HTTPException(status_code=401, detail="visual_sidecar_unauthorized")


def _multipart_frame(index: int, frame: bytes) -> bytes:
    digest = sha256(frame).hexdigest()
    head = (
        f"--{_BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(frame)}\r\n"
        f"X-Frame-Index: {index}\r\n"
        f"X-Frame-Sha256: {digest}\r\n"
        "\r\n"
    ).encode("ascii")
    return head + frame + b"\r\n"


def create_ditto_visual_sidecar_app(
    *,
    engine: RealtimeVisualEngine,
    auth_token: str,
    max_reference_image_bytes: int = 8_000_000,
    max_audio_bytes: int = 12_000_000,
    max_frame_bytes: int = 512_000,
    max_frames_per_turn: int = 9_000,
    temp_root: str | Path = "/tmp/empire-ditto-register",
) -> FastAPI:
    token = str(auth_token or "").strip()
    if len(token.encode("utf-8")) < 32:
        raise ValueError("visual sidecar auth token must be at least 32 bytes")
    if min(
        max_reference_image_bytes,
        max_audio_bytes,
        max_frame_bytes,
        max_frames_per_turn,
    ) <= 0:
        raise ValueError("visual sidecar limits must be positive")

    root = Path(temp_root)
    app = FastAPI(
        title="Empire Ditto Visual Sidecar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    def health(authorization: str | None = Header(default=None)):
        _authorized(token, authorization)
        return {
            "ok": True,
            "engine": engine.engine_name,
            "model_ref": engine.model_ref,
            "stream_format": "multipart-jpeg",
            "raw_reference_media_persisted_by_api": False,
            "raw_turn_audio_persisted_by_api": False,
            "meeting_transport_present": False,
            "speech_execution": False,
            "commercial_execution": False,
            "execution_authority": "render_only",
        }

    @app.post("/v1/avatars/register")
    def register(
        req: VisualRegisterRequest,
        authorization: str | None = Header(default=None),
    ):
        _authorized(token, authorization)
        if not _AVATAR_ID.fullmatch(req.avatar_id):
            raise HTTPException(status_code=422, detail="invalid_avatar_id")
        if not req.consent_evidence_ref.strip():
            raise HTTPException(status_code=422, detail="consent_evidence_required")
        try:
            image = base64.b64decode(
                req.source_image_base64,
                validate=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail="invalid_source_image_base64",
            ) from exc
        if not image or len(image) > max_reference_image_bytes:
            raise HTTPException(
                status_code=413,
                detail="source_image_size_invalid",
            )
        if engine.avatar_exists(req.avatar_id):
            return {
                "registered": True,
                "duplicate": True,
                "avatar_id": req.avatar_id,
                "raw_reference_media_persisted_by_api": False,
            }

        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=root,
                prefix="visual-register-",
                suffix=".img",
                delete=False,
            ) as handle:
                handle.write(image)
                handle.flush()
                os.fsync(handle.fileno())
                path = Path(handle.name)
            os.chmod(path, 0o600)
            engine.register_avatar(
                avatar_id=req.avatar_id,
                source_image_path=str(path),
            )
        finally:
            if path is not None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass

        return {
            "registered": True,
            "duplicate": False,
            "avatar_id": req.avatar_id,
            "raw_reference_media_persisted_by_api": False,
        }

    @app.post("/v1/render-stream")
    async def render_stream(
        request: Request,
        authorization: str | None = Header(default=None),
        x_empire_avatar_id: str | None = Header(default=None),
        x_empire_audio_sha256: str | None = Header(default=None),
        x_empire_sample_rate: str | None = Header(default=None),
        x_empire_target_fps: str | None = Header(default=None),
        x_empire_model_ref: str | None = Header(default=None),
    ):
        _authorized(token, authorization)
        avatar_id = str(x_empire_avatar_id or "").strip()
        audio_sha = str(x_empire_audio_sha256 or "").strip().lower()
        model_ref = str(x_empire_model_ref or "").strip()
        if not _AVATAR_ID.fullmatch(avatar_id):
            raise HTTPException(status_code=422, detail="invalid_avatar_id")
        if not _SHA256.fullmatch(audio_sha):
            raise HTTPException(status_code=422, detail="audio_sha256_invalid")
        if model_ref != engine.model_ref:
            raise HTTPException(status_code=422, detail="visual_model_ref_mismatch")
        if not engine.avatar_exists(avatar_id):
            raise HTTPException(status_code=404, detail="avatar_id_not_registered")
        try:
            sample_rate = int(str(x_empire_sample_rate or "0"))
            target_fps = int(str(x_empire_target_fps or "0"))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="visual_render_numeric_header_invalid",
            ) from exc
        if sample_rate < 8000 or sample_rate > 48000:
            raise HTTPException(status_code=422, detail="sample_rate_invalid")
        if target_fps < 20 or target_fps > 60:
            raise HTTPException(status_code=422, detail="target_fps_invalid")

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_audio_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="visual_audio_size_invalid",
                    )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="content_length_invalid",
                ) from exc
        pcm = await request.body()
        if not pcm or len(pcm) > max_audio_bytes or len(pcm) % 2:
            raise HTTPException(
                status_code=413,
                detail="visual_audio_size_invalid",
            )
        if sha256(pcm).hexdigest() != audio_sha:
            raise HTTPException(status_code=409, detail="audio_sha256_mismatch")

        def stream():
            count = 0
            for index, frame in enumerate(
                engine.stream_jpeg_frames(
                    avatar_id=avatar_id,
                    pcm=pcm,
                    sample_rate=sample_rate,
                    target_fps=target_fps,
                )
            ):
                count += 1
                if count > max_frames_per_turn:
                    raise RuntimeError("visual frame count exceeds configured limit")
                if (
                    not isinstance(frame, (bytes, bytearray))
                    or not frame
                    or len(frame) > max_frame_bytes
                ):
                    raise RuntimeError("visual frame violates configured limit")
                yield _multipart_frame(index, bytes(frame))
            yield f"--{_BOUNDARY}--\r\n".encode("ascii")

        return StreamingResponse(
            stream(),
            media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
            headers={
                "Cache-Control": "no-store",
                "X-Visual-Engine": engine.engine_name,
                "X-Visual-Model": engine.model_ref,
                "X-Avatar-Id": avatar_id,
                "X-Execution-Authority": "render_only",
                "X-Raw-Audio-Persisted": "false",
            },
        )

    return app


def _load_engine_factory(spec: str):
    raw = str(spec or "").strip()
    if ":" not in raw:
        raise RuntimeError(
            "EMPIRE_DITTO_ENGINE_FACTORY must be module:function"
        )
    module_name, name = raw.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, name, None)
    if not callable(factory):
        raise RuntimeError("Ditto engine factory is not callable")
    return factory


def app_from_env() -> FastAPI:
    auth = os.getenv("EMPIRE_DITTO_AUTH_TOKEN", "").strip()
    factory = _load_engine_factory(
        os.getenv("EMPIRE_DITTO_ENGINE_FACTORY", "")
    )
    engine = factory(dict(os.environ))
    return create_ditto_visual_sidecar_app(
        engine=engine,
        auth_token=auth,
        max_reference_image_bytes=int(
            os.getenv("EMPIRE_DITTO_MAX_REFERENCE_IMAGE_BYTES", "8000000")
        ),
        max_audio_bytes=int(
            os.getenv("EMPIRE_DITTO_MAX_AUDIO_BYTES", "12000000")
        ),
        max_frame_bytes=int(
            os.getenv("EMPIRE_DITTO_MAX_FRAME_BYTES", "512000")
        ),
        max_frames_per_turn=int(
            os.getenv("EMPIRE_DITTO_MAX_FRAMES_PER_TURN", "9000")
        ),
        temp_root=os.getenv(
            "EMPIRE_DITTO_TEMP_ROOT",
            "/var/lib/empire-ditto/tmp",
        ),
    )
