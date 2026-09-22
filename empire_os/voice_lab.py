"""Empire Voice Lab: self-hosted STT, closer reasoning and TTS.

No third-party speech vendor is required. Models are loaded lazily so the
normal EmpireOS API can start even when the optional voice runtime is absent.
"""
from __future__ import annotations

from array import array
from dataclasses import asdict, dataclass
import math
import os
import sys
from typing import Any


@dataclass(frozen=True)
class VoiceLabConfig:
    stt_backend: str = "faster_whisper"
    stt_model: str = "small.en"
    tts_backend: str = "kokoro"
    tts_voice: str = "af_heart"
    device: str = "cpu"
    compute_type: str = "int8"
    input_rate: int = 16000
    output_rate: int = 16000
    silence_ms: int = 650
    min_speech_ms: int = 280
    rms_threshold: int = 420

    @classmethod
    def from_env(cls) -> "VoiceLabConfig":
        return cls(
            stt_backend=os.getenv(
                "EMPIRE_VOICE_STT_BACKEND", "faster_whisper"
            ).strip(),
            stt_model=os.getenv(
                "EMPIRE_VOICE_STT_MODEL", "small.en"
            ).strip(),
            tts_backend=os.getenv(
                "EMPIRE_VOICE_TTS_BACKEND", "kokoro"
            ).strip(),
            tts_voice=os.getenv(
                "EMPIRE_VOICE_TTS_VOICE", "af_heart"
            ).strip(),
            device=os.getenv(
                "EMPIRE_VOICE_DEVICE", "cpu"
            ).strip(),
            compute_type=os.getenv(
                "EMPIRE_VOICE_COMPUTE_TYPE", "int8"
            ).strip(),
            silence_ms=int(os.getenv("EMPIRE_VOICE_SILENCE_MS", "650")),
            min_speech_ms=int(os.getenv("EMPIRE_VOICE_MIN_SPEECH_MS", "280")),
            rms_threshold=int(os.getenv("EMPIRE_VOICE_RMS_THRESHOLD", "420")),
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
    mean_square = sum(int(v) * int(v) for v in samples) / len(samples)
    return math.sqrt(mean_square)


class VoiceTurnDetector:
    """Tiny streaming VAD/turn detector for 16 kHz PCM16 phone audio."""

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


class FasterWhisperSTT:
    def __init__(self, config: VoiceLabConfig) -> None:
        self.config = config
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise VoiceLabRuntimeError(
                    "faster-whisper is not installed"
                ) from exc
            self._model = WhisperModel(
                self.config.stt_model,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
        return self._model

    def transcribe(self, pcm16: bytes) -> str:
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceLabRuntimeError("numpy is required for STT") from exc
        audio = (
            np.frombuffer(pcm16, dtype="<i2")
            .astype(np.float32)
            / 32768.0
        )
        segments, _info = self._load().transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()


class KokoroTTS:
    SOURCE_RATE = 24000

    def __init__(self, config: VoiceLabConfig) -> None:
        self.config = config
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
            except ImportError as exc:
                raise VoiceLabRuntimeError(
                    "kokoro is not installed"
                ) from exc
            self._pipeline = KPipeline(lang_code="a")
        return self._pipeline

    def synthesize(self, text: str) -> bytes:
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceLabRuntimeError("numpy is required for TTS") from exc

        chunks = []
        for _graphemes, _phonemes, audio in self._load()(
            text,
            voice=self.config.tts_voice,
            speed=1.0,
        ):
            chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            return b""

        audio = np.concatenate(chunks)
        if self.SOURCE_RATE != self.config.output_rate:
            out_len = max(
                1,
                round(
                    len(audio)
                    * self.config.output_rate
                    / self.SOURCE_RATE
                ),
            )
            old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
            new = np.linspace(0.0, 1.0, out_len, endpoint=False)
            audio = np.interp(new, old, audio).astype(np.float32)
        pcm = np.clip(audio, -1.0, 1.0)
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
            timeout=int(os.getenv("EMPIRE_VOICE_LLM_TIMEOUT", "12")),
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
        if self.config.stt_backend != "faster_whisper":
            raise VoiceLabRuntimeError("unsupported Empire STT backend")
        if self.config.tts_backend != "kokoro":
            raise VoiceLabRuntimeError("unsupported Empire TTS backend")
        self.stt = FasterWhisperSTT(self.config)
        self.tts = KokoroTTS(self.config)
        self.brain = VoiceCloserBrain()

    @staticmethod
    def dependency_readiness() -> dict[str, Any]:
        import importlib.util
        return {
            "faster_whisper": (
                importlib.util.find_spec("faster_whisper") is not None
            ),
            "kokoro": importlib.util.find_spec("kokoro") is not None,
            "numpy": importlib.util.find_spec("numpy") is not None,
        }

    def readiness(self) -> dict[str, Any]:
        deps = self.dependency_readiness()
        configured = all(deps.values())
        return {
            "engine": "empire_voice_lab",
            "ownership": "self_hosted",
            "speech_vendor": None,
            "stt": self.config.stt_backend,
            "stt_model": self.config.stt_model,
            "tts": self.config.tts_backend,
            "tts_voice": self.config.tts_voice,
            "sample_rate": self.config.output_rate,
            "dependencies": deps,
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
