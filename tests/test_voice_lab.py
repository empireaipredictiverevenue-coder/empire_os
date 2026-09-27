import struct

import numpy as np

from empire_os.voice_lab import (
    SherpaKokoroTTS,
    VoiceLabConfig,
    VoiceTurnDetector,
    pcm16_rms,
)


def frame(value: int, samples: int = 320) -> bytes:
    return struct.pack("<" + "h" * samples, *([value] * samples))


def test_pcm16_rms_detects_speech_energy():
    assert pcm16_rms(frame(0)) == 0
    assert pcm16_rms(frame(1200)) > 1000


def test_turn_detector_emits_bounded_utterance_after_silence():
    detector = VoiceTurnDetector(
        VoiceLabConfig(
            silence_ms=100,
            min_speech_ms=60,
            rms_threshold=300,
        )
    )

    event, audio = detector.feed(frame(1200))
    assert event == "speech_start"
    assert audio is None

    detector.feed(frame(1200))
    detector.feed(frame(1200))

    emitted = None
    for _ in range(5):
        event, audio = detector.feed(frame(0))
        if event == "utterance":
            emitted = audio
            break

    assert emitted is not None
    assert len(emitted) >= 3 * 640


def test_voice_lab_dependencies_are_reported_without_loading_models():
    from empire_os.voice_lab import EmpireVoiceLab

    readiness = EmpireVoiceLab.dependency_readiness()
    assert set(readiness) == {"sherpa_onnx", "numpy"}
    assert all(isinstance(value, bool) for value in readiness.values())



def test_opening_discloses_ai_identity_and_opt_out():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = object.__new__(EmpireVoiceLab)
    text = lab.opening_text(business_name="Acme Roofing")
    lower = text.lower()
    assert "ai assistant" in lower
    assert "empire ai" in lower
    assert "acme roofing" in lower
    assert "stop calling" in lower


def test_kokoro_stream_emits_pcm_before_generation_finishes(monkeypatch):
    config = VoiceLabConfig(num_threads=4, output_rate=16000)
    tts = SherpaKokoroTTS(config)
    callback_returns = []

    class FakeTTS:
        sample_rate = 24000

        def generate(self, text, generation, callback):
            assert text == "Hi. There."
            callback_returns.append(
                callback(np.full(2400, 0.1, dtype=np.float32), 0.5)
            )
            callback_returns.append(
                callback(np.full(2400, 0.2, dtype=np.float32), 1.0)
            )
            return object()

    monkeypatch.setattr(tts, "_load", lambda: FakeTTS())

    chunks = []
    stats = tts.stream(
        "Hi. There.",
        lambda pcm, progress: chunks.append((pcm, progress)),
    )

    assert callback_returns == [1, 1]
    assert [progress for _, progress in chunks] == [0.5, 1.0]
    assert all(isinstance(pcm, bytes) and pcm for pcm, _ in chunks)
    assert stats["chunks"] == 2
    assert stats["pcm_bytes"] == sum(len(pcm) for pcm, _ in chunks)
    assert stats["stopped"] is False


def test_kokoro_stream_honours_barge_in_stop(monkeypatch):
    config = VoiceLabConfig(num_threads=4, output_rate=16000)
    tts = SherpaKokoroTTS(config)
    stopped = False
    callback_returns = []

    class FakeTTS:
        sample_rate = 24000

        def generate(self, text, generation, callback):
            callback_returns.append(
                callback(np.full(2400, 0.1, dtype=np.float32), 0.5)
            )
            return object()

    monkeypatch.setattr(tts, "_load", lambda: FakeTTS())

    def on_chunk(_pcm, _progress):
        nonlocal stopped
        stopped = True

    stats = tts.stream(
        "Hi.",
        on_chunk,
        should_stop=lambda: stopped,
    )

    assert callback_returns == [0]
    assert stats["chunks"] == 1
    assert stats["stopped"] is True


def test_voice_lab_ambiguous_transcript_never_reaches_closer():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = EmpireVoiceLab()
    lab.stt.transcribe = lambda _pcm: (
        "Empire Voice Lab test. Now external voice vendor is being used."
    )
    class FakeVerifier:
        def transcribe(self, _pcm):
            return "Empire Voice Lab test. Now external voice vendor is being used."
    lab.verifier_stt = FakeVerifier()

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("closer must not run for ambiguous transcript")

    lab.brain.reply = should_not_run
    result = lab.respond_text(b"pcm")

    assert result["decision"]["action"] == "clarify"
    assert result["decision"]["requires_clarification"] is True
    assert "repeat" in result["response_text"].lower()


def test_voice_lab_opt_out_never_reaches_closer():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = EmpireVoiceLab()
    lab.stt.transcribe = lambda _pcm: "Please do not call me again."
    class FakeVerifier:
        def transcribe(self, _pcm):
            return "Please do not call me again."
    lab.verifier_stt = FakeVerifier()

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("closer must not run for opt-out")

    lab.brain.reply = should_not_run
    result = lab.respond_text(b"pcm")

    assert result["decision"]["action"] == "stop"
    assert result["decision"]["suppression_requested"] is True
    assert "end the call" in result["response_text"].lower()


def test_voice_lab_safe_interest_routes_to_closer():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = EmpireVoiceLab()
    lab.stt.transcribe = lambda _pcm: "Yes, send me the brief by email."
    class FakeVerifier:
        def transcribe(self, _pcm):
            return "YES SEND ME THE BRIEF BY EMAIL"
    lab.verifier_stt = FakeVerifier()
    lab.brain.reply = lambda *_args, **_kwargs: "Absolutely."

    result = lab.respond_text(b"pcm")

    assert result["decision"]["action"] == "continue"
    assert result["decision"]["intent"] == "follow_up_permission"
    assert result["response_text"] == "Absolutely."


def test_voice_lab_dual_asr_price_disagreement_forces_clarification():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = EmpireVoiceLab()
    lab.stt.transcribe = lambda _pcm: "The pilot is 1500 pounds."

    class FakeVerifier:
        def transcribe(self, _pcm):
            return "THE PILOT IS 500 POUNDS"

    lab.verifier_stt = FakeVerifier()

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("closer must not run on price disagreement")

    lab.brain.reply = should_not_run
    result = lab.respond_text(b"pcm")

    assert result["decision"]["action"] == "clarify"
    assert "asr_disagreement:numbers" in result["decision"]["risk_flags"]
    assert "asr_disagreement:money" in result["decision"]["risk_flags"]
    assert [item["source"] for item in result["asr_candidates"]] == [
        "sherpa_whisper",
        "sherpa_zipformer",
    ]


def test_voice_lab_dual_asr_preserves_both_candidates_when_safe():
    from empire_os.voice_lab import EmpireVoiceLab

    lab = EmpireVoiceLab()
    lab.stt.transcribe = lambda _pcm: "Yes, send me the brief by email."

    class FakeVerifier:
        def transcribe(self, _pcm):
            return "YES SEND ME THE BRIEF BY EMAIL"

    lab.verifier_stt = FakeVerifier()
    lab.brain.reply = lambda *_args, **_kwargs: "Absolutely."

    result = lab.respond_text(b"pcm")

    assert result["decision"]["action"] == "continue"
    assert result["decision"]["candidate_count"] == 2
    assert len(result["asr_candidates"]) == 2
    assert result["transcript"] == "Yes, send me the brief by email."
