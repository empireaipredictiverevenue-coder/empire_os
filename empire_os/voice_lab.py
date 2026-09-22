"""Empire Voice Lab: self-hosted speech stack for Python 3.14.

Speech runtime:
- sherpa-onnx Whisper for local STT
- sherpa-onnx Kokoro for local TTS
- no third-party speech API
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
import importlib.util
import math
import os
from pathlib import Path
import sys
from typing import Any


MODEL_ROOT = Path(
    os.getenv(
        "EMPIRE_VOICE_MODEL_ROOT",
        "/srv/empire_os/runtime/models/voice_lab",
    )
)


@dataclass(frozen=True)
class VoiceLabConfig:
    stt_backend: str = "sherpa_whisper"
    stt_model_dir: str = str(
        MODEL_ROOT / "sherpa-onnx-whisper-tiny.en"
    )
    tts_backend: str = "sherpa_kokoro"
    tts_model_dir: str = str(
        MODEL_ROOT / "kokoro-en-v0_19"
    )
    tts_voice: str = "empire_default"
    tts_sid: int = 10
    provider: str = "cpu"
    num_threads: int = 2
    input_rate: int = 16000
    output_rate: int = 16000
    silence_ms: int = 650
    min_speech_ms: int = 280
    rms_threshold: int = 420

    @classmethod
    def from_env(cls) -> "VoiceLabConfig":
        return cls(
            stt_backend=os.getenv(
                "EMPIRE_VOICE_STT_BACKEND",
                "sherpa_whisper",
            ).strip(),
            stt_model_dir=os.getenv(
                "EMPIRE_VOICE_STT_MODEL_DIR",
                str(MODEL_ROOT / "sherpa-onnx-whisper-tiny.en"),
            ).strip(),
            tts_backend=os.getenv(
                "EMPIRE_VOICE_TTS_BACKEND",
                "sherpa_kokoro",
            ).strip(),
            tts_model_dir=os.getenv(
                "EMPIRE_VOICE_TTS_MODEL_DIR",
                str(MODEL_ROOT / "kokoro-en-v0_19"),
            ).strip(),
            tts_voice=os.getenv(
                "EMPIRE_VOICE_TTS_VOICE",
                "empire_default",
            ).strip(),
            tts_sid=int(
                os.getenv("EMPIRE_VOICE_TTS_SID", "10")
            ),
            provider=os.getenv(
                "EMPIRE_VOICE_PROVIDER", "cpu"
            ).strip(),
            num_threads=max(
                1,
                int(os.getenv("EMPIRE_VOICE_NUM_THREADS", "2")),
            ),
            silence_ms=int(
                os.getenv("EMPIRE_VOICE_SILENCE_MS", "650")
            ),
            min_speech_ms=int(
                os.getenv("EMPIRE_VOICE_MIN_SPEECH_MS", "280")
            ),
            rms_threshold=int(
                os.getenv("EMPIRE_VOICE_RMS_THRESHOLD", "420")
            ),
        )


class VoiceLabRuntimeError(RuntimeError):
    pass


def pcm16_rms(frame: bytes) -> float:
    if not frame:
        return 0.0
    samples = array("h")
    samples.frombytes(frame[: len(frame) - (len(frame) % 2)])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    mean_square = sum(
        int(v) * int(v) for v in samples
    ) / len(samples)
    return math.sqrt(mean_square)


class VoiceTurnDetector:
    """Streaming turn detector for 16 kHz PCM16 phone audio."""

    def __init__(self, config: VoiceLabConfig | None = None) -> None:
        self.config = config or VoiceLabConfig.from_env()
        self._frames: list[bytes] = []
        self._speech_ms = 0
        self._silence_ms = 0
        self._in_speech = False

    def feed(self, frame: bytes) -> tuple[str, bytes | None]:
        frame_ms = max(
            1,
            round(
                len(frame)
                / 2
                / self.config.input_rate
                * 1000
            ),
        )
        voiced = pcm16_rms(frame) >= self.config.rms_threshold

        if voiced:
            self._frames.append(frame)
            self._speech_ms += frame_ms
            self._silence_ms = 0
            event = "speech_start" if not self._in_speech else "speech"
            self._in_speech = True
            return event, None

        if not self._in_speech:
            return "silence", None

        self._frames.append(frame)
        self._silence_ms += frame_ms
        if self._silence_ms < self.config.silence_ms:
            return "speech", None

        audio = b"".join(self._frames)
        speech_ms = self._speech_ms
        self._frames = []
        self._speech_ms = 0
        self._silence_ms = 0
        self._in_speech = False

        if speech_ms < self.config.min_speech_ms:
            return "discard", None
        return "utterance", audio


def _require_file(path: Path, label: str) -> str:
    if not path.is_file():
        raise VoiceLabRuntimeError(
            f"{label} missing: {path}"
        )
    return str(path)


class SherpaWhisperSTT:
    def __init__(self, config: VoiceLabConfig) -> None:
        self.config = config
        self._recognizer = None

    def _load(self):
        if self._recognizer is not None:
            return self._recognizer
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "sherpa-onnx is not installed"
            ) from exc

        root = Path(self.config.stt_model_dir)
        encoder = root / "tiny.en-encoder.int8.onnx"
        decoder = root / "tiny.en-decoder.int8.onnx"
        tokens = root / "tiny.en-tokens.txt"
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=_require_file(encoder, "Whisper encoder"),
            decoder=_require_file(decoder, "Whisper decoder"),
            tokens=_require_file(tokens, "Whisper tokens"),
            num_threads=self.config.num_threads,
            provider=self.config.provider,
            debug=False,
        )
        return self._recognizer

    def transcribe(self, pcm16: bytes) -> str:
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "numpy is required for STT"
            ) from exc

        audio = (
            np.frombuffer(pcm16, dtype="<i2")
            .astype(np.float32)
            / 32768.0
        )
        if audio.size == 0:
            return ""
        recognizer = self._load()
        stream = recognizer.create_stream()
        stream.accept_waveform(self.config.input_rate, audio)
        recognizer.decode_stream(stream)
        return str(stream.result.text or "").strip()


class SherpaKokoroTTS:
    SOURCE_RATE = 24000

    def __init__(self, config: VoiceLabConfig) -> None:
        self.config = config
        self._tts = None

    def _load(self):
        if self._tts is not None:
            return self._tts
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "sherpa-onnx is not installed"
            ) from exc

        root = Path(self.config.tts_model_dir)
        tts_config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=_require_file(
                        root / "model.onnx", "Kokoro model"
                    ),
                    voices=_require_file(
                        root / "voices.bin", "Kokoro voices"
                    ),
                    tokens=_require_file(
                        root / "tokens.txt", "Kokoro tokens"
                    ),
                    data_dir=str(root / "espeak-ng-data"),
                    lexicon="",
                ),
                provider=self.config.provider,
                debug=False,
                num_threads=self.config.num_threads,
            ),
            max_num_sentences=1,
        )
        if not tts_config.validate():
            raise VoiceLabRuntimeError(
                "invalid sherpa Kokoro configuration"
            )
        self._tts = sherpa_onnx.OfflineTts(tts_config)
        return self._tts

    def synthesize(self, text: str) -> bytes:
        try:
            import numpy as np
            import sherpa_onnx
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "sherpa-onnx and numpy are required for TTS"
            ) from exc

        generation = sherpa_onnx.GenerationConfig()
        generation.sid = self.config.tts_sid
        generation.speed = 1.0
        generation.silence_scale = 0.2

        audio = self._load().generate(
            str(text or "").strip(),
            generation,
        )
        samples = np.asarray(audio.samples, dtype=np.float32)
        if samples.size == 0:
            return b""

        source_rate = int(audio.sample_rate or self.SOURCE_RATE)
        if source_rate != self.config.output_rate:
            out_len = max(
                1,
                round(
                    len(samples)
                    * self.config.output_rate
                    / source_rate
                ),
            )
            old = np.linspace(
                0.0, 1.0, len(samples), endpoint=False
            )
            new = np.linspace(
                0.0, 1.0, out_len, endpoint=False
            )
            samples = np.interp(
                new, old, samples
            ).astype(np.float32)

        pcm = np.clip(samples, -1.0, 1.0)
        return (pcm * 32767.0).astype("<i2").tobytes()


class VoiceCloserBrain:
    SYSTEM = """You are Empire AI's phone concierge for B2B outreach.
Your job is to identify the decision maker, understand whether there is a real
business problem or opportunity, and earn permission for a useful follow-up.

Rules:
- Never invent demand, customers, results, volume, pricing or availability.
- Never claim payment, acceptance, exclusivity or a binding commercial term.
- Do not pressure the person. Respect opt-out or disinterest immediately.
- Keep each spoken response short: normally 1-3 sentences.
- If you reached the wrong person, politely ask who owns growth/revenue.
- If there is interest, offer the free one-page evidence brief and ask the
  minimum useful qualification question.
- Never pretend to be human. If asked, say you are Empire AI's AI assistant.
"""

    def __init__(self) -> None:
        from empire_os.agent_core import OllamaClient
        self.client = OllamaClient(
            base_url=os.getenv(
                "EMPIRE_VOICE_LLM_BASE_URL",
                "http://127.0.0.1:11434",
            ),
            model=os.getenv(
                "EMPIRE_VOICE_LLM_MODEL",
                "qwen2.5:7b",
            ),
            timeout=int(
                os.getenv("EMPIRE_VOICE_LLM_TIMEOUT", "12")
            ),
        )

    def reply(
        self,
        transcript: str,
        *,
        business_name: str = "",
        niche: str = "",
        metro: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> str:
        context = (
            f"Business: {business_name or 'unknown'}; "
            f"niche: {niche or 'unknown'}; "
            f"market: {metro or 'unknown'}."
        )
        messages = list(history or [])[-8:]
        messages.append({
            "role": "user",
            "content": context + "\nCaller said: " + transcript,
        })
        answer = self.client.chat(
            messages,
            system=self.SYSTEM,
            temperature=0.25,
        ).strip()
        if not answer or answer.startswith('{"error"'):
            return (
                "Thanks. I don’t want to guess here. "
                "Would it be alright if I send the short evidence brief "
                "and we follow up from there?"
            )
        return answer[:900]


class EmpireVoiceLab:
    def __init__(self, config: VoiceLabConfig | None = None) -> None:
        self.config = config or VoiceLabConfig.from_env()
        if self.config.stt_backend != "sherpa_whisper":
            raise VoiceLabRuntimeError(
                "unsupported Empire STT backend"
            )
        if self.config.tts_backend != "sherpa_kokoro":
            raise VoiceLabRuntimeError(
                "unsupported Empire TTS backend"
            )
        self.stt = SherpaWhisperSTT(self.config)
        self.tts = SherpaKokoroTTS(self.config)
        self.brain = VoiceCloserBrain()

    def opening_text(self, *, business_name: str = "") -> str:
        target = (
            f" at {business_name}"
            if str(business_name or "").strip()
            else ""
        )
        return (
            "Hi, this is Empire AI's AI assistant calling on behalf of "
            "Empire AI. I'm trying to reach the person responsible for "
            f"growth or new business{target}. "
            "If you'd rather not receive calls from us, just say stop calling."
        )

    def synthesize_text(self, text: str) -> bytes:
        return self.tts.synthesize(str(text or "").strip())

    @staticmethod
    def dependency_readiness() -> dict[str, Any]:
        return {
            "sherpa_onnx": (
                importlib.util.find_spec("sherpa_onnx") is not None
            ),
            "numpy": importlib.util.find_spec("numpy") is not None,
        }

    @staticmethod
    def model_readiness(
        config: VoiceLabConfig | None = None,
    ) -> dict[str, bool]:
        cfg = config or VoiceLabConfig.from_env()
        stt = Path(cfg.stt_model_dir)
        tts = Path(cfg.tts_model_dir)
        return {
            "stt_encoder": (
                stt / "tiny.en-encoder.int8.onnx"
            ).is_file(),
            "stt_decoder": (
                stt / "tiny.en-decoder.int8.onnx"
            ).is_file(),
            "stt_tokens": (
                stt / "tiny.en-tokens.txt"
            ).is_file(),
            "tts_model": (tts / "model.onnx").is_file(),
            "tts_voices": (tts / "voices.bin").is_file(),
            "tts_tokens": (tts / "tokens.txt").is_file(),
            "tts_espeak_data": (tts / "espeak-ng-data").is_dir(),
        }

    def readiness(self) -> dict[str, Any]:
        deps = self.dependency_readiness()
        models = self.model_readiness(self.config)
        configured = all(deps.values()) and all(models.values())
        return {
            "engine": "empire_voice_lab",
            "ownership": "self_hosted",
            "speech_vendor": None,
            "stt": self.config.stt_backend,
            "stt_model_dir": self.config.stt_model_dir,
            "tts": self.config.tts_backend,
            "tts_model_dir": self.config.tts_model_dir,
            "tts_voice": self.config.tts_voice,
            "sample_rate": self.config.output_rate,
            "dependencies": deps,
            "models": models,
            "configured": configured,
            "execution_allowed": configured,
        }

    def respond(
        self,
        pcm16: bytes,
        *,
        business_name: str = "",
        niche: str = "",
        metro: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        transcript = self.stt.transcribe(pcm16)
        if not transcript:
            return {
                "transcript": "",
                "response_text": "",
                "audio": b"",
            }
        response_text = self.brain.reply(
            transcript,
            business_name=business_name,
            niche=niche,
            metro=metro,
            history=history,
        )
        audio = self.tts.synthesize(response_text)
        return {
            "transcript": transcript,
            "response_text": response_text,
            "audio": audio,
        }
