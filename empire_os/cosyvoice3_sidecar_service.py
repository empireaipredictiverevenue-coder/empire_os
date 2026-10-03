"""Authenticated CosyVoice3 GPU sidecar for Empire Digital Avatar.

Designed to run on a separate GPU host. Raw clone reference audio is accepted
only during registration, written to a private temporary file, converted into
CosyVoice speaker state, then deleted.
"""
from __future__ import annotations

import base64
import hmac
from hashlib import sha256
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Protocol

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


_VOICE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class CosyVoiceEngine(Protocol):
    @property
    def model_ref(self) -> str:
        ...

    @property
    def sample_rate(self) -> int:
        ...

    def voice_exists(self, voice_id: str) -> bool:
        ...

    def register_voice(
        self,
        *,
        voice_id: str,
        prompt_text: str,
        prompt_wav_path: str,
    ) -> None:
        ...

    def stream_pcm(
        self,
        *,
        voice_id: str,
        text: str,
    ) -> Iterable[bytes]:
        ...


class VoiceRegisterRequest(BaseModel):
    voice_id: str
    prompt_text: str = Field(min_length=1, max_length=4000)
    reference_audio_base64: str
    consent_evidence_ref: str = Field(min_length=1, max_length=512)


class VoiceRenderRequest(BaseModel):
    render_id: str = Field(min_length=1, max_length=256)
    engine: str
    model_ref: str
    voice_id: str
    text: str = Field(min_length=1, max_length=4000)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: str = Field(default="en", min_length=1, max_length=32)
    output_format: str = "pcm_s16le"
    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    stream: bool = True


class CosyVoice3Adapter:
    def __init__(
        self,
        *,
        model_dir: str,
        fp16: bool = True,
    ) -> None:
        try:
            from cosyvoice.cli.cosyvoice import AutoModel
        except ImportError as exc:
            raise RuntimeError("CosyVoice is not installed on GPU sidecar") from exc
        self._model_ref = str(model_dir)
        self._model = AutoModel(
            model_dir=model_dir,
            fp16=fp16,
        )

    @property
    def model_ref(self) -> str:
        return self._model_ref

    @property
    def sample_rate(self) -> int:
        return int(self._model.sample_rate)

    def voice_exists(self, voice_id: str) -> bool:
        return voice_id in set(self._model.list_available_spks())

    def register_voice(
        self,
        *,
        voice_id: str,
        prompt_text: str,
        prompt_wav_path: str,
    ) -> None:
        ok = self._model.add_zero_shot_spk(
            prompt_text,
            prompt_wav_path,
            voice_id,
        )
        if ok is not True:
            raise RuntimeError("CosyVoice speaker registration failed")
        self._model.save_spkinfo()

    def stream_pcm(
        self,
        *,
        voice_id: str,
        text: str,
    ) -> Iterable[bytes]:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("numpy required on voice sidecar") from exc

        for output in self._model.inference_zero_shot(
            text,
            "",
            "",
            zero_shot_spk_id=voice_id,
            stream=True,
        ):
            speech = output.get("tts_speech")
            if speech is None:
                continue
            values = speech.detach().cpu().numpy().reshape(-1)
            pcm = (
                np.clip(values, -1.0, 1.0) * 32767.0
            ).astype("<i2").tobytes()
            if pcm:
                yield pcm


def create_cosyvoice3_sidecar_app(
    *,
    engine: CosyVoiceEngine,
    auth_token: str,
    max_reference_audio_bytes: int = 12_000_000,
    temp_root: str | Path = "/tmp/empire-cosyvoice-register",
) -> FastAPI:
    token = str(auth_token or "").strip()
    if not token:
        raise ValueError("CosyVoice sidecar auth token required")
    if max_reference_audio_bytes <= 0:
        raise ValueError("max_reference_audio_bytes must be positive")
    tmp_root = Path(temp_root)

    app = FastAPI(
        title="Empire CosyVoice3 Sidecar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def authorize(authorization: str | None) -> None:
        supplied = str(authorization or "")
        expected = "Bearer " + token
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="voice_sidecar_unauthorized")

    @app.get("/health")
    def health(authorization: str | None = Header(default=None)):
        authorize(authorization)
        return {
            "ok": True,
            "engine": "cosyvoice3",
            "sample_rate": engine.sample_rate,
            "raw_reference_media_persisted_by_api": False,
            "meeting_transport_present": False,
            "execution_authority": "render_only",
        }

    @app.post("/v1/voices/register")
    def register(
        req: VoiceRegisterRequest,
        authorization: str | None = Header(default=None),
    ):
        authorize(authorization)
        if not _VOICE_ID.fullmatch(req.voice_id):
            raise HTTPException(status_code=422, detail="invalid_voice_id")
        if not req.consent_evidence_ref.strip():
            raise HTTPException(status_code=422, detail="consent_evidence_required")
        try:
            audio = base64.b64decode(
                req.reference_audio_base64,
                validate=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail="invalid_reference_audio_base64",
            ) from exc
        if not audio or len(audio) > max_reference_audio_bytes:
            raise HTTPException(
                status_code=413,
                detail="reference_audio_size_invalid",
            )

        if engine.voice_exists(req.voice_id):
            return {
                "registered": True,
                "duplicate": True,
                "voice_id": req.voice_id,
                "raw_reference_media_persisted_by_api": False,
            }

        tmp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(tmp_root, 0o700)
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=tmp_root,
                prefix="voice-register-",
                suffix=".wav",
                delete=False,
            ) as handle:
                handle.write(audio)
                handle.flush()
                os.fsync(handle.fileno())
                path = Path(handle.name)
            os.chmod(path, 0o600)
            engine.register_voice(
                voice_id=req.voice_id,
                prompt_text=req.prompt_text,
                prompt_wav_path=str(path),
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
            "voice_id": req.voice_id,
            "raw_reference_media_persisted_by_api": False,
        }


    @app.post("/v1/render")
    def render(
        req: VoiceRenderRequest,
        authorization: str | None = Header(default=None),
    ):
        authorize(authorization)
        if req.engine.lower() != "cosyvoice3":
            raise HTTPException(status_code=422, detail="unsupported_voice_engine")
        if sha256(req.text.encode("utf-8")).hexdigest() != req.text_sha256:
            raise HTTPException(status_code=422, detail="text_sha256_mismatch")
        if req.model_ref != engine.model_ref:
            raise HTTPException(status_code=422, detail="voice_model_ref_mismatch")
        if not _VOICE_ID.fullmatch(req.voice_id):
            raise HTTPException(status_code=422, detail="invalid_voice_id")
        if not engine.voice_exists(req.voice_id):
            raise HTTPException(status_code=404, detail="voice_id_not_registered")
        if req.output_format != "pcm_s16le" or req.stream is not True:
            raise HTTPException(status_code=422, detail="streaming_pcm_required")
        if req.sample_rate != engine.sample_rate:
            raise HTTPException(status_code=422, detail="sample_rate_mismatch")

        return StreamingResponse(
            engine.stream_pcm(
                voice_id=req.voice_id,
                text=req.text,
            ),
            media_type=f"audio/L16;rate={engine.sample_rate}",
            headers={
                "X-Empire-Render-Id": req.render_id,
                "X-Voice-Engine": "cosyvoice3",
                "X-Voice-Id": req.voice_id,
            },
        )

    return app


def app_from_env() -> FastAPI:
    model_dir = os.getenv(
        "EMPIRE_COSYVOICE3_MODEL_DIR",
        "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    ).strip()
    auth = os.getenv("EMPIRE_COSYVOICE3_AUTH_TOKEN", "").strip()
    fp16 = os.getenv(
        "EMPIRE_COSYVOICE3_FP16",
        "1",
    ).strip().lower() in {"1", "true", "yes", "on"}
    engine = CosyVoice3Adapter(
        model_dir=model_dir,
        fp16=fp16,
    )
    return create_cosyvoice3_sidecar_app(
        engine=engine,
        auth_token=auth,
        max_reference_audio_bytes=int(
            os.getenv(
                "EMPIRE_COSYVOICE3_MAX_REFERENCE_AUDIO_BYTES",
                "12000000",
            )
        ),
        temp_root=os.getenv(
            "EMPIRE_COSYVOICE3_TEMP_ROOT",
            "/var/lib/empire-cosyvoice/tmp",
        ),
    )
