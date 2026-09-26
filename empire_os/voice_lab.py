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
from typing import Any, Callable

from empire_os.decision_judge import (
    ACTION_CLARIFY,
    ACTION_HUMAN_HANDOFF,
    ACTION_STOP,
    INTENT_OPT_OUT,
    EmpireDecisionJudge,
    TranscriptCandidate,
)


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
    verifier_stt_model_dir: str = str(
        MODEL_ROOT
        / "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
    )
    tts_backend: str = "sherpa_kokoro"
    tts_model_dir: str = str(
        MODEL_ROOT / "kokoro-en-v0_19"
    )
    tts_model_file: str = "model.onnx"
    tts_voice: str = "empire_default"
    tts_sid: int = 10
    provider: str = "cpu"
    num_threads: int = 4
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
            verifier_stt_model_dir=os.getenv(
                "EMPIRE_VOICE_VERIFIER_STT_MODEL_DIR",
                str(
                    MODEL_ROOT
                    / "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
                ),
            ).strip(),
            tts_backend=os.getenv(
                "EMPIRE_VOICE_TTS_BACKEND",
                "sherpa_kokoro",
            ).strip(),
            tts_model_dir=os.getenv(
                "EMPIRE_VOICE_TTS_MODEL_DIR",
                str(MODEL_ROOT / "kokoro-en-v0_19"),
            ).strip(),
            tts_model_file=os.getenv(
                "EMPIRE_VOICE_TTS_MODEL_FILE",
                "model.onnx",
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
                int(os.getenv("EMPIRE_VOICE_NUM_THREADS", "4")),
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


class SherpaZipformerVerifierSTT:
    """Independent local ASR verifier used by Empire Decision Judge."""

    REQUIRED_FILES = (
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
        "tokens.txt",
    )

    def __init__(self, config: VoiceLabConfig) -> None:
        self.config = config
        self._recognizer = None

    @classmethod
    def ready(cls, config: VoiceLabConfig) -> bool:
        root = Path(config.verifier_stt_model_dir)
        return all((root / name).is_file() for name in cls.REQUIRED_FILES)

    def _load(self):
        if self._recognizer is not None:
            return self._recognizer
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "sherpa-onnx is not installed"
            ) from exc

        root = Path(self.config.verifier_stt_model_dir)
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=_require_file(root / "tokens.txt", "Zipformer tokens"),
            encoder=_require_file(
                root / "encoder-epoch-99-avg-1.int8.onnx",
                "Zipformer encoder",
            ),
            decoder=_require_file(
                root / "decoder-epoch-99-avg-1.onnx",
                "Zipformer decoder",
            ),
            joiner=_require_file(
                root / "joiner-epoch-99-avg-1.int8.onnx",
                "Zipformer joiner",
            ),
            num_threads=self.config.num_threads,
            sample_rate=self.config.input_rate,
            decoding_method="greedy_search",
            provider=self.config.provider,
        )
        return self._recognizer

    def transcribe(self, pcm16: bytes) -> str:
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "numpy is required for verifier STT"
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
        stream.accept_waveform(
            self.config.input_rate,
            np.zeros(
                int(0.5 * self.config.input_rate),
                dtype=np.float32,
            ),
        )
        stream.input_finished()
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
        return str(recognizer.get_result(stream) or "").strip()


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
                        root / self.config.tts_model_file,
                        "Kokoro model",
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

    def _samples_to_pcm16(
        self,
        samples: Any,
        *,
        source_rate: int,
    ) -> bytes:
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "numpy is required for TTS"
            ) from exc

        values = np.asarray(samples, dtype=np.float32)
        if values.size == 0:
            return b""

        if source_rate != self.config.output_rate:
            out_len = max(
                1,
                round(
                    len(values)
                    * self.config.output_rate
                    / source_rate
                ),
            )
            old_axis = np.linspace(
                0.0, 1.0, len(values), endpoint=False
            )
            new_axis = np.linspace(
                0.0, 1.0, out_len, endpoint=False
            )
            values = np.interp(
                new_axis, old_axis, values
            ).astype(np.float32)

        pcm = np.clip(values, -1.0, 1.0)
        return (pcm * 32767.0).astype("<i2").tobytes()

    def _generation_config(self):
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise VoiceLabRuntimeError(
                "sherpa-onnx is required for TTS"
            ) from exc

        generation = sherpa_onnx.GenerationConfig()
        generation.sid = self.config.tts_sid
        generation.speed = 1.0
        generation.silence_scale = 0.2
        return generation

    def synthesize(self, text: str) -> bytes:
        tts = self._load()
        audio = tts.generate(
            str(text or "").strip(),
            self._generation_config(),
        )
        source_rate = int(
            audio.sample_rate
            or getattr(tts, "sample_rate", 0)
            or self.SOURCE_RATE
        )
        return self._samples_to_pcm16(
            audio.samples,
            source_rate=source_rate,
        )

    def stream(
        self,
        text: str,
        on_chunk: Callable[[bytes, float], None],
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Generate Kokoro speech and emit sentence-sized PCM chunks.

        sherpa-onnx invokes the callback after each configured sentence
        batch. max_num_sentences=1 keeps first-audio latency bounded by the
        first sentence instead of the whole reply.
        """
        content = str(text or "").strip()
        if not content:
            return {"chunks": 0, "pcm_bytes": 0, "stopped": False}

        tts = self._load()
        source_rate = int(
            getattr(tts, "sample_rate", 0) or self.SOURCE_RATE
        )
        chunks = 0
        pcm_bytes = 0
        stopped = False

        def callback(samples, progress: float) -> int:
            nonlocal chunks, pcm_bytes, stopped
            if should_stop is not None and should_stop():
                stopped = True
                return 0
            pcm = self._samples_to_pcm16(
                samples,
                source_rate=source_rate,
            )
            if pcm:
                chunks += 1
                pcm_bytes += len(pcm)
                on_chunk(pcm, float(progress))
            if should_stop is not None and should_stop():
                stopped = True
                return 0
            # sherpa-onnx core uses 0=stop and non-zero=continue.
            return 1

        tts.generate(
            content,
            self._generation_config(),
            callback,
        )
        return {
            "chunks": chunks,
            "pcm_bytes": pcm_bytes,
            "stopped": stopped,
        }


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
        self.verifier_stt = (
            SherpaZipformerVerifierSTT(self.config)
            if SherpaZipformerVerifierSTT.ready(self.config)
            else None
        )
        self.tts = SherpaKokoroTTS(self.config)
        self.brain = VoiceCloserBrain()
        self.judge = EmpireDecisionJudge()

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

    def stream_text(
        self,
        text: str,
        on_chunk: Callable[[bytes, float], None],
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        return self.tts.stream(
            str(text or "").strip(),
            on_chunk,
            should_stop=should_stop,
        )

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
        verifier = Path(cfg.verifier_stt_model_dir)
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
            "verifier_stt_encoder": (
                verifier / "encoder-epoch-99-avg-1.int8.onnx"
            ).is_file(),
            "verifier_stt_decoder": (
                verifier / "decoder-epoch-99-avg-1.onnx"
            ).is_file(),
            "verifier_stt_joiner": (
                verifier / "joiner-epoch-99-avg-1.int8.onnx"
            ).is_file(),
            "verifier_stt_tokens": (
                verifier / "tokens.txt"
            ).is_file(),
            "tts_model": (tts / cfg.tts_model_file).is_file(),
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
            "verifier_stt": (
                "sherpa_zipformer"
                if self.verifier_stt is not None
                else None
            ),
            "verifier_stt_model_dir": (
                self.config.verifier_stt_model_dir
            ),
            "tts": self.config.tts_backend,
            "tts_model_dir": self.config.tts_model_dir,
            "tts_model_file": self.config.tts_model_file,
            "tts_voice": self.config.tts_voice,
            "sample_rate": self.config.output_rate,
            "dependencies": deps,
            "models": models,
            "configured": configured,
            "execution_allowed": configured,
        }

    def respond_text(
        self,
        pcm16: bytes,
        *,
        business_name: str = "",
        niche: str = "",
        metro: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        transcript = self.stt.transcribe(pcm16)
        verifier_transcript = (
            self.verifier_stt.transcribe(pcm16)
            if self.verifier_stt is not None
            else ""
        )

        asr_candidates: list[dict[str, str]] = []
        judge_candidates: list[TranscriptCandidate] = []
        if transcript:
            asr_candidates.append({
                "source": self.config.stt_backend,
                "text": transcript,
            })
            judge_candidates.append(
                TranscriptCandidate(
                    source=self.config.stt_backend,
                    text=transcript,
                )
            )
        if verifier_transcript:
            asr_candidates.append({
                "source": "sherpa_zipformer",
                "text": verifier_transcript,
            })
            judge_candidates.append(
                TranscriptCandidate(
                    source="sherpa_zipformer",
                    text=verifier_transcript,
                )
            )

        canonical_transcript = transcript or verifier_transcript
        if not canonical_transcript:
            return {
                "transcript": "",
                "response_text": "",
                "decision": None,
                "asr_candidates": [],
            }

        decision = self.judge.judge_candidates(judge_candidates)
        decision_payload = decision.to_dict()

        if decision.action == ACTION_STOP:
            if decision.intent == INTENT_OPT_OUT:
                response_text = (
                    "Understood. I'll end the call now."
                )
            else:
                response_text = (
                    "Understood. Thanks for your time."
                )
        elif decision.action == ACTION_CLARIFY:
            response_text = (
                "I want to make sure I heard you correctly. "
                "Could you repeat that?"
            )
        elif decision.action == ACTION_HUMAN_HANDOFF:
            response_text = (
                "Thanks. I don't want to make a binding commitment "
                "on this call. A human can handle that."
            )
        else:
            response_text = self.brain.reply(
                canonical_transcript,
                business_name=business_name,
                niche=niche,
                metro=metro,
                history=history,
            )

        return {
            "transcript": canonical_transcript,
            "response_text": response_text,
            "decision": decision_payload,
            "asr_candidates": asr_candidates,
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
        result = self.respond_text(
            pcm16,
            business_name=business_name,
            niche=niche,
            metro=metro,
            history=history,
        )
        response_text = str(result.get("response_text") or "")
        audio = (
            self.tts.synthesize(response_text)
            if response_text
            else b""
        )
        return {
            **result,
            "audio": audio,
        }
