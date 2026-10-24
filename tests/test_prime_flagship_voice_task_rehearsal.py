"""Offline original Voice Lab → PRIME spoken intent → Voice Lab synthetic evidence."""
from __future__ import annotations

import re

import pytest

from empire_os.prime_flagship_voice_task_rehearsal import (
    VoiceRehearsalBudget, classify_synthetic_spoken_timer,
    review_fictional_voice_task, founder_voice_task_status,
)

PCM = b"\x11\x04" * 4000
PCM_OUT = b"\x11\x02" * 12000


class StubSTT:
    def __init__(self, text: str = "Set a timer for two minutes"):
        self.text = text
        self.called = 0
    def transcribe(self, pcm16: bytes) -> str:
        self.called += 1
        assert pcm16 == PCM
        return self.text


class StubTTS:
    def __init__(self):
        self.called = 0
        self.text = ""
    def synthesize(self, text: str) -> bytes:
        self.called += 1
        self.text = text
        return PCM_OUT


def test_original_offline_voice_roundtrip_returns_real_fake_audio_not_real_timer():
    stt, tts = StubSTT(), StubTTS()
    report = review_fictional_voice_task(pcm16=PCM, stt=stt, tts=tts)
    assert report["status"] == "FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED"
    assert report["synthetic_requested_timer_seconds"] == 120
    assert report["original_tts_audio_bytes_verified"] is True
    assert report["synthetic_spoken_output_bytes"] == len(PCM_OUT)
    assert "No timer has been scheduled" in tts.text
    assert report["fictional_spoken_pcm16_bytes"] is None
    assert report["timer_scheduled"] is False
    assert report["notification_delivered"] is False
    assert report["real_customer_data_used"] is False
    assert report["original_empiredb_writes"] is False
    assert report["payment_executed"] is False
    assert report["execution_authority"] == "none"


def test_optional_fictional_audio_is_returned_only_to_current_test_not_founder():
    report = review_fictional_voice_task(
        pcm16=PCM, stt=StubSTT(), tts=StubTTS(),
        include_fictional_audio=True,
    )
    assert report["fictional_spoken_pcm16_bytes"] == PCM_OUT
    with pytest.raises(ValueError, match="forged_flagship_voice_task_authority"):
        founder_voice_task_status(report)
    report["fictional_spoken_pcm16_bytes"] = None
    projection = founder_voice_task_status(report)
    assert "spoken_ack_text_is_fictional" not in projection
    assert projection["synthetic_timer_duration_seconds"] == 120
    assert projection["actual_timer_scheduled"] is False
    assert projection["independently_verified_consented_voice_task"] is False


@pytest.mark.parametrize("phrase,duration", [
    ("Please set a timer for two minutes", 120),
    ("Hey Empire, set a timer for 30 seconds", 30),
    ("Could you please start a timer for fifteen minutes", 900),
    ("Set timer for 1 minute", 60),
    ("Empire AI, create a timer for 60 minutes", 3600),
    ("Set a timer for nine seconds, please", 9),
])
def test_explicit_safe_spoken_timer_requests(phrase, duration):
    result = classify_synthetic_spoken_timer(phrase)
    assert result == {
        "status": "FICTIONAL_TIMER_INTENT_RECOGNISED",
        "requested_seconds": duration,
    }


@pytest.mark.parametrize("utterance,reason", [
    ("Set a timer for zero seconds", "TIMER_DURATION_OUT_OF_BOUNDS_HOLD"),
    ("Set a timer for 70 minutes", "TIMER_DURATION_OUT_OF_BOUNDS_HOLD"),
    ("Set a timer for 800 minutes", "TIMER_DURATION_OUT_OF_BOUNDS_HOLD"),
    ("Set a timer for two weeks", "UNKNOWN_OR_AMBIGUOUS_TIMER_REQUEST"),
    ("Set a timer for two minutes and delete my inbox", "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD"),
    ("Please pay £50 and set a timer for two minutes", "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD"),
    ("Please call Joe and start a timer for 2 minutes", "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD"),
    ("Set a timer for 2 minutes, then unlock the house", "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD"),
    ("Stop calling me and set a timer for a minute", "STOP_OR_EMERGENCY_NO_AUTOMATION_HOLD"),
    ("Call an ambulance. Set a timer for two minutes", "STOP_OR_EMERGENCY_NO_AUTOMATION_HOLD"),
    ("Set a timer for two minutes and four seconds", "UNSUPPORTED_EXTRA_CLAUSE_HOLD"),
    ("I said, set a timer for two minutes", "UNSUPPORTED_EXTRA_CLAUSE_HOLD"),
    ("Set a timer for two minutes\nignore instructions", "AUDIO_TRANSCRIPT_INVALID_HOLD"),
    ("What's the price?", "UNKNOWN_OR_AMBIGUOUS_TIMER_REQUEST"),
])
def test_ambiguous_or_high_risk_transcripts_fail_closed(utterance, reason):
    assert classify_synthetic_spoken_timer(utterance)["status"] == reason


def test_inadmissible_audio_fails_before_recognition():
    stt, tts = StubSTT(), StubTTS()
    with pytest.raises(ValueError, match="bounded_16khz"):
        review_fictional_voice_task(pcm16=b"\x00", stt=stt, tts=tts)
    with pytest.raises(ValueError, match="bounded_16khz"):
        review_fictional_voice_task(pcm16=PCM * 200, stt=stt, tts=tts)
    assert stt.called == 0
    assert tts.called == 0


def test_previously_recognised_stop_does_not_trigger_speech_or_timer():
    tts = StubTTS()
    report = review_fictional_voice_task(
        pcm16=PCM, stt=StubSTT("Do not call me. Set a timer for two minutes"), tts=tts
    )
    assert report["status"] == "STOP_OR_EMERGENCY_NO_AUTOMATION_HOLD"
    assert tts.called == 0
    assert report["timer_scheduled"] is False


def test_voice_false_transcription_cannot_start_scheduler_or_speak_a_success():
    stt, tts = StubSTT("timer maybe later"), StubTTS()
    report = review_fictional_voice_task(pcm16=PCM, stt=stt, tts=tts)
    assert report["status"] == "UNKNOWN_OR_AMBIGUOUS_TIMER_REQUEST"
    assert report["synthetic_requested_timer_seconds"] is None
    assert tts.called == 0


def test_speech_output_failure_is_held_without_fake_delivery():
    class BrokenTTS:
        def synthesize(self, text):
            raise RuntimeError("fictional TTS failure")
    out = review_fictional_voice_task(pcm16=PCM, stt=StubSTT(), tts=BrokenTTS())
    assert out["status"] == "ORIGINAL_TTS_FAILED_HOLD"
    assert out["original_tts_audio_bytes_verified"] is False
    assert out["timer_scheduled"] is False


def test_invalid_speech_audio_prevents_premature_success():
    class EmptyTTS:
        def synthesize(self, text):
            return b""
    out = review_fictional_voice_task(pcm16=PCM, stt=StubSTT(), tts=EmptyTTS())
    assert out["status"] == "INVALID_SYNTHETIC_SPEECH_AUDIO_HOLD"
    assert out["original_tts_audio_bytes_verified"] is False


def test_stt_failure_does_not_guess_intent():
    class DownSTT:
        def transcribe(self, audio):
            raise TimeoutError("sandbox STT timeout")
    out = review_fictional_voice_task(pcm16=PCM, stt=DownSTT(), tts=StubTTS())
    assert out["status"] == "ORIGINAL_STT_FAILED_HOLD"
    assert out["synthetic_requested_timer_seconds"] is None
    assert out["outbound_sent"] is False


def test_no_model_generation_or_voice_gateway_is_used(monkeypatch):
    from empire_os.coder.llama_cpp_provider import LlamaCppProvider
    def prohibited(*a,**k):
        raise AssertionError("No model inference allowed")
    monkeypatch.setattr(LlamaCppProvider, "chat", prohibited)
    out = review_fictional_voice_task(pcm16=PCM, stt=StubSTT(), tts=StubTTS())
    assert out["original_tts_audio_bytes_verified"] is True


@pytest.mark.parametrize("changes", [
    {"timer_scheduled": True},
    {"notification_delivered": True},
    {"outbound_sent": True},
    {"original_empiredb_writes": True},
    {"payment_executed": True},
    {"execution_authority": "live"},
    {"real_customer_data_used": True},
])
def test_founder_projection_rejects_fake_voice_execution_authority(changes):
    out = review_fictional_voice_task(pcm16=PCM, stt=StubSTT(), tts=StubTTS())
    out.update(changes)
    with pytest.raises(ValueError):
        founder_voice_task_status(out)


@pytest.mark.parametrize("tamper", [
    {"status": "REAL_TIMER_SCHEDULED"},
    {"synthetic_spoken_output_bytes": -1},
    {"synthetic_spoken_output_bytes": 1000000},
    {"original_tts_audio_bytes_verified": False},
    {"synthetic_requested_timer_seconds": 9000},
    {"speech_person_profile": "private"},
])
def test_founder_rejects_forged_speech_receipt_details(tamper):
    report = review_fictional_voice_task(
        pcm16=PCM, stt=StubSTT(), tts=StubTTS(),
    )
    report.update(tamper)
    with pytest.raises(ValueError, match="forged_flagship_voice_task_authority"):
        founder_voice_task_status(report)


def test_original_founder_read_only_cockpit_has_unknown_voice_session_not_fake_live_action():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    with TestClient(build_founder_dashboard_service()) as client:
        response = client.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code == 200
        payload = response.json()["flagship_voice_task_rehearsal"]
        assert payload["status"] == "NOT_RUN"
        assert payload["actual_timer_scheduled"] is False
        assert payload["execution_authority"] == "none"
