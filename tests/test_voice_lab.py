import struct

from empire_os.voice_lab import (
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
    assert set(readiness) == {"faster_whisper", "kokoro", "numpy"}
    assert all(isinstance(value, bool) for value in readiness.values())
