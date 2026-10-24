"""Exact local-only timer expiry receipts, replay protection, cancellation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import pytest

from empire_os.prime_flagship_local_timer_pilot import (
    InMemoryTimerPilot, InMemorySink, LocalTimerHold,
    rehearse_voice_to_local_timer,
)


class Clock:
    def __init__(self, initial=1000.0):
        self.value = float(initial)
    def __call__(self):
        return self.value
    def advance(self, n):
        self.value += n


class STT:
    def __init__(self, text="Set a timer for two seconds"):
        self.text = text
        self.calls = 0
    def transcribe(self, pcm):
        self.calls += 1
        return self.text


class TTS:
    def __init__(self):
        self.calls = 0
        self.last_text = None
    def synthesize(self,text):
        self.calls += 1
        self.last_text = text
        return b"\x01\x01" * 4096


PCM = b"\x02\x01" * 320


def setup():
    clock = Clock()
    sink = InMemorySink()
    timer = InMemoryTimerPilot(clock=clock, sink=sink)
    return clock, sink, timer


def test_full_original_voice_to_actual_local_memory_timer_expiry_receipt():
    clock, sink, timer = setup()
    speech = STT()
    voice = TTS()
    result = rehearse_voice_to_local_timer(
        pcm16=PCM, stt=speech, tts=voice,
        timer=timer, request_key="sim_example_one",
        explicit_synthetic_run=True,
    )
    assert result["status"] == "IN_MEMORY_TIMER_STARTED_NOT_REAL_DELIVERY"
    assert result["synthetic_timer_seconds"] == 2
    assert result["spoken_ack_pcm16_bytes"] == 8192
    assert "No reminder was sent" in voice.last_text
    assert timer.inspect(request_key="sim_example_one")["state"] == "SYNTHETIC_SCHEDULED_IN_MEMORY"
    clock.advance(1.99)
    assert timer.poll_due(explicit_synthetic_run=True) == []
    assert sink.events == []
    clock.advance(0.01)
    receipts = timer.poll_due(explicit_synthetic_run=True)
    assert len(receipts) == 1
    assert receipts[0]["state"] == "LOCAL_SINK_ACKNOWLEDGED_ONLY"
    assert receipts[0]["local_sink_receipt"]
    assert receipts[0]["real_reminder_delivered"] is False
    assert receipts[0]["real_user_notification_sent"] is False
    assert sink.events[0]["kind"] == "LOCAL_TIMER_EXPIRED"
    assert sink.events[0]["external_delivery"] is False
    assert timer.poll_due(explicit_synthetic_run=True) == []
    assert len(sink.events) == 1
    assert result["execution_authority"] == "test_local_memory_only"


def test_cancel_before_expiry_does_not_fire_even_if_monotonic_time_passes():
    clock, sink, timer = setup()
    timer.create(request_key="sim_cancel_me",duration_seconds=3,explicit_synthetic_run=True)
    receipt = timer.cancel(request_key="sim_cancel_me")
    assert receipt["state"] == "SYNTHETIC_CANCELLED"
    assert timer.cancel(request_key="sim_cancel_me") == receipt
    clock.advance(100)
    assert timer.poll_due(explicit_synthetic_run=True) == []
    assert sink.events == []


def test_no_new_key_after_cancel_or_ack_prevents_replay():
    clock, sink, timer = setup()
    timer.create(request_key="sim_replay_one", duration_seconds=1,explicit_synthetic_run=True)
    timer.cancel(request_key="sim_replay_one")
    with pytest.raises(LocalTimerHold, match="replayed_request"):
        timer.create(request_key="sim_replay_one", duration_seconds=1,explicit_synthetic_run=True)
    timer.create(request_key="sim_replay_two", duration_seconds=1,explicit_synthetic_run=True)
    clock.advance(2)
    timer.poll_due(explicit_synthetic_run=True)
    with pytest.raises(LocalTimerHold, match="replayed_request"):
        timer.create(request_key="sim_replay_two", duration_seconds=1,explicit_synthetic_run=True)


def test_local_sink_exception_terminal_no_hidden_retry():
    class FailingSink:
        def __init__(self):
            self.calls=0
        def emit_local(self,event):
            self.calls+=1
            raise OSError("offline sink cannot accept event")
    clock = Clock()
    sink=FailingSink()
    timer=InMemoryTimerPilot(clock=clock,sink=sink)
    timer.create(request_key="sim_sink_failure", duration_seconds=1,explicit_synthetic_run=True)
    clock.advance(1)
    result=timer.poll_due(explicit_synthetic_run=True)
    assert result[0]["state"] == "LOCAL_SINK_FAILED_NO_RETRY"
    assert result[0]["local_sink_receipt"] is None
    assert timer.poll_due(explicit_synthetic_run=True) == []
    assert sink.calls == 1


def test_explicit_synthetic_gate_is_required_for_schedule_and_poll():
    clock,sink,timer=setup()
    with pytest.raises(LocalTimerHold,match="explicit_synthetic"):
        timer.create(request_key="sim_explicit",duration_seconds=2,explicit_synthetic_run=False)
    with pytest.raises(LocalTimerHold,match="explicit_synthetic"):
        timer.poll_due(explicit_synthetic_run=False)
    assert sink.events==[]


@pytest.mark.parametrize("duration",[-1,0,3601,1.5,"2",True])
def test_invalid_duration_cannot_schedule_local_timer(duration):
    _,sink,timer=setup()
    with pytest.raises(LocalTimerHold,match="bounded_synthetic"):
        timer.create(request_key="sim_bad_duration",duration_seconds=duration,explicit_synthetic_run=True)
    assert sink.events==[]


@pytest.mark.parametrize("key",[
    "someone@example.test","root", "abc", "sim_x", "http://local",
    "sim_ALICE", "sim_" + "a"*33,
])
def test_nonfictional_or_unbounded_task_identifiers_rejected(key):
    _,sink,timer=setup()
    with pytest.raises(LocalTimerHold,match="opaque_synthetic"):
        timer.create(request_key=key,duration_seconds=1,explicit_synthetic_run=True)
    assert sink.events==[]


def test_finite_monotonic_clock_cannot_be_rewound_to_manipulate_timer():
    clock,sink,timer=setup()
    timer.create(request_key="sim_clock_check",duration_seconds=2,explicit_synthetic_run=True)
    clock.advance(-10)
    with pytest.raises(LocalTimerHold,match="clock_regression"):
        timer.poll_due(explicit_synthetic_run=True)
    assert sink.events == []


def test_bounded_memory_capacity_no_unlimited_job_loop():
    clock,sink,timer=setup()
    for i in range(12):
        timer.create(request_key=f"sim_timer_{i}",duration_seconds=3,explicit_synthetic_run=True)
    with pytest.raises(LocalTimerHold,match="bounded_sandbox_timer_session_capacity"):
        timer.create(request_key="sim_timer_12",duration_seconds=3,explicit_synthetic_run=True)
    clock.advance(3)
    receipts=timer.poll_due(explicit_synthetic_run=True)
    assert len(receipts)==12
    assert len({x["local_sink_receipt"] for x in receipts})==12
    assert len(sink.events)==12
    assert not timer.poll_due(explicit_synthetic_run=True)


def test_concurrent_polls_never_double_fire_same_synthetic_timer():
    clock,sink,timer=setup()
    timer.create(request_key="sim_concurrent",duration_seconds=1,explicit_synthetic_run=True)
    clock.advance(1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(timer.poll_due,explicit_synthetic_run=True) for _ in range(8)]
    all_receipts=[item for f in futures for item in f.result()]
    assert len(all_receipts)==1
    assert len(sink.events)==1
    assert all_receipts[0]["state"]=="LOCAL_SINK_ACKNOWLEDGED_ONLY"


@pytest.mark.parametrize("text",[
    "Please unsubscribe me. Set a timer for two seconds",
    "Send £500 to someone and set a timer for 2 seconds",
    "Tell the police to come. Set a timer for 2 seconds",
    "Set a timer for two weeks",
])
def test_unsafe_or_unrecognised_speech_never_schedules(text):
    clock,sink,timer=setup()
    stt=STT(text)
    tts=TTS()
    result=rehearse_voice_to_local_timer(
        pcm16=PCM,stt=stt,tts=tts,timer=timer,
        request_key="sim_unsafe_request",explicit_synthetic_run=True,
    )
    assert result["timer_created"] is False
    assert result["real_reminder_delivered"] is False
    assert tts.calls==0
    assert sink.events==[]


def test_tts_failure_cannot_leave_silent_timer_behind():
    class BrokenTTS:
        def synthesize(self,text):
            raise RuntimeError("test offline TTS failure")
    _,_,timer=setup()
    result=rehearse_voice_to_local_timer(
        pcm16=PCM,stt=STT(),tts=BrokenTTS(),
        timer=timer,request_key="sim_speech_failure",
        explicit_synthetic_run=True,
    )
    assert result["status"]=="ORIGINAL_TTS_FAILED_HOLD"
    assert result["timer_created"] is False
    with pytest.raises(LocalTimerHold,match="no_original_synthetic_timer_to_inspect"):
        timer.inspect(request_key="sim_speech_failure")


def test_speech_replay_fails_even_if_fresh_audio_is_provided():
    _,_,timer=setup()
    kw=dict(pcm16=PCM,stt=STT(),tts=TTS(),timer=timer,
            request_key="sim_repeated_voice",explicit_synthetic_run=True)
    rehearse_voice_to_local_timer(**kw)
    with pytest.raises(LocalTimerHold,match="replayed_request"):
        rehearse_voice_to_local_timer(**kw)


def test_voice_pilot_is_not_enabled_on_founder_get_api():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    with TestClient(build_founder_dashboard_service()) as client:
        r=client.get("/v1/founder-dashboard/prime-digital-twin")
        assert r.status_code==200
        assert r.json()["flagship_voice_task_rehearsal"]["status"]=="NOT_RUN"
        assert r.json()["flagship_release_readiness"]["launch_approved"] is False
        assert client.post("/v1/founder-dashboard/prime-digital-twin").status_code==405
