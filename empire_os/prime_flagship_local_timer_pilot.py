"""Original PRIME Voice Lab: bounded, real in-process synthetic timer pilot.

This is NOT a reminder service, persistent scheduler, notification channel,
user consent receipt, owner-authorised tool executor or production activation.
It uses monotonic due times, an explicitly injected in-memory sink, replay
refusal, fail-closed delivery and cancellation. No network, daemon, DB,
cron, contacts, devices, or background timer threads are created.

An acknowledged local sink invocation verifies LOCAL DELIVERY ONLY, never
mobile/email/voice notification. No timestamps/names/addresses persist.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any, Callable, Protocol
import re

from empire_os.agi_capabilities import review_capability_request
from empire_os.prime_flagship_voice_task_rehearsal import (
    Recognizer, Speaker, classify_synthetic_spoken_timer,
    MAX_AUDIO_BYTES, MAX_SPOKEN_RESPONSE_BYTES,
)

SCHEMA = "empire.prime.original_local_timer_pilot.v1"
KEY = re.compile(r"^sim_[a-z0-9_-]{3,32}$")
MAX_TIMERS = 12


class LocalTimerHold(ValueError):
    pass


class LocalReceiptSink(Protocol):
    def emit_local(self, event: dict[str, Any]) -> bool: ...


@dataclass(frozen=True)
class _Job:
    request_key: str
    duration_seconds: int
    due_monotonic: float
    state: str
    local_receipt_id: str | None = None


class InMemoryTimerPilot:
    """Synthetic-only original assistant component; no automatic worker."""

    def __init__(self, *, clock: Callable[[], float] = monotonic,
                 sink: LocalReceiptSink):
        if not callable(clock) or not callable(getattr(sink, "emit_local", None)):
            raise LocalTimerHold("sandbox_clock_and_local_sink_required")
        self._clock = clock
        self._sink = sink
        self._lock = Lock()
        self._jobs: dict[str, _Job] = {}
        self._max_monotonic: float | None = None

    def _time(self) -> float:
        now = self._clock()
        if type(now) not in (int, float) or not (0 <= now < float("inf")):
            raise LocalTimerHold("finite_monotonic_sandbox_clock_required")
        if self._max_monotonic is not None and now < self._max_monotonic:
            raise LocalTimerHold("sandbox_clock_regression_refused")
        self._max_monotonic = float(now)
        return float(now)

    @staticmethod
    def _id(request_key: str, kind: str) -> str:
        # Test-only opaque event ID; NOT a signed original-owner receipt.
        return sha256(("synthetic-in-process-only:v1:"+request_key+":"+kind).encode()).hexdigest()

    @staticmethod
    def _record(job: _Job) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "mode": "SYNTHETIC_LOCAL_ONLY",
            "state": job.state,
            "synthetic_timer_key": job.request_key,
            "duration_seconds": job.duration_seconds,
            "local_sink_receipt": job.local_receipt_id,
            "persistent_scheduler_connected": False,
            "local_sink_receipt_not_external_delivery": True,
            "real_reminder_delivered": False,
            "real_user_notification_sent": False,
            "empiredb_writes": False,
            "execution_authority": "test_local_memory_only",
        }

    def create(self, *, request_key: str, duration_seconds: int,
               explicit_synthetic_run: bool) -> dict[str, Any]:
        if type(explicit_synthetic_run) is not bool or explicit_synthetic_run is not True:
            raise LocalTimerHold("explicit_synthetic_local_timer_run_required")
        if type(request_key) is not str or KEY.fullmatch(request_key) is None:
            raise LocalTimerHold("opaque_synthetic_timer_key_required")
        if type(duration_seconds) is not int or not 1 <= duration_seconds <= 3600:
            raise LocalTimerHold("bounded_synthetic_timer_duration_required")
        with self._lock:
            if request_key in self._jobs:
                # Never reuse the key even after cancellation, due time, failure.
                raise LocalTimerHold("original_local_timer_replayed_request_refused")
            if len(self._jobs) >= MAX_TIMERS:
                raise LocalTimerHold("bounded_sandbox_timer_session_capacity")
            now = self._time()
            job = _Job(request_key, duration_seconds,
                       now + duration_seconds, "SYNTHETIC_SCHEDULED_IN_MEMORY")
            self._jobs[request_key] = job
            return self._record(job)

    def cancel(self, *, request_key: str) -> dict[str, Any]:
        if type(request_key) is not str or KEY.fullmatch(request_key) is None:
            raise LocalTimerHold("opaque_synthetic_timer_key_required")
        with self._lock:
            # Read clock even for cancellation; a regressed time is a hold.
            self._time()
            old = self._jobs.get(request_key)
            if old is None:
                raise LocalTimerHold("no_original_synthetic_timer_to_cancel")
            if old.state == "SYNTHETIC_CANCELLED":
                return self._record(old)  # duplicate CANCEL is safe and idempotent
            if old.state != "SYNTHETIC_SCHEDULED_IN_MEMORY":
                raise LocalTimerHold("timer_already_dispatched_cannot_be_cancelled")
            updated = _Job(old.request_key, old.duration_seconds,
                           old.due_monotonic, "SYNTHETIC_CANCELLED")
            self._jobs[request_key] = updated
            return self._record(updated)

    def inspect(self, *, request_key: str) -> dict[str, Any]:
        if type(request_key) is not str or KEY.fullmatch(request_key) is None:
            raise LocalTimerHold("opaque_synthetic_timer_key_required")
        with self._lock:
            job = self._jobs.get(request_key)
            if job is None:
                raise LocalTimerHold("no_original_synthetic_timer_to_inspect")
            return self._record(job)

    def poll_due(self, *, explicit_synthetic_run: bool) -> list[dict[str, Any]]:
        """One synchronous local poll; scheduler owner never runs automatically.

        Jobs are marked DISPATCHING *before* emitting the event so concurrent
        threads cannot deliver the same expiration twice. A sink exception
        moves to terminal failure, never invisible automatic retry.
        """
        if type(explicit_synthetic_run) is not bool or explicit_synthetic_run is not True:
            raise LocalTimerHold("explicit_synthetic_local_timer_run_required")
        with self._lock:
            now = self._time()
            due: list[_Job] = []
            for key, old in self._jobs.items():
                if old.state == "SYNTHETIC_SCHEDULED_IN_MEMORY" and now >= old.due_monotonic:
                    self._jobs[key] = _Job(old.request_key, old.duration_seconds,
                                            old.due_monotonic, "LOCAL_DISPATCH_IN_PROGRESS")
                    due.append(old)
        receipts: list[dict[str, Any]] = []
        for original in due:
            receipt_id = self._id(original.request_key, "local_expired")
            event = {
                "schema_version": "empire.prime.local_timer_sink_event.v1",
                "mode": "SYNTHETIC_LOCAL_ONLY",
                "local_event_id": receipt_id,
                "synthetic_timer_key": original.request_key,
                "kind": "LOCAL_TIMER_EXPIRED",
                "real_user_notification": False,
                "external_delivery": False,
            }
            try:
                delivered = self._sink.emit_local(event) is True
            except Exception:
                delivered = False
            final = "LOCAL_SINK_ACKNOWLEDGED_ONLY" if delivered else "LOCAL_SINK_FAILED_NO_RETRY"
            with self._lock:
                self._jobs[original.request_key] = _Job(
                    original.request_key, original.duration_seconds,
                    original.due_monotonic, final,
                    receipt_id if delivered else None,
                )
                receipts.append(self._record(self._jobs[original.request_key]))
        return receipts


class InMemorySink:
    """One-shot test/local-only sink. Stores no phone, contact or audio."""
    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def emit_local(self, event: dict[str, Any]) -> bool:
        if (type(event) is not dict or event.get("mode") != "SYNTHETIC_LOCAL_ONLY"
            or event.get("kind") != "LOCAL_TIMER_EXPIRED"
            or event.get("external_delivery") is not False
            or event.get("real_user_notification") is not False):
            return False
        event_id = event.get("local_event_id")
        if type(event_id) is not str or event_id in self._ids:
            return False
        self._ids.add(event_id)
        self.events.append(dict(event))
        return True


def rehearse_voice_to_local_timer(
    *, pcm16: bytes, stt: Recognizer, tts: Speaker,
    timer: InMemoryTimerPilot, request_key: str,
    explicit_synthetic_run: bool,
) -> dict[str, Any]:
    """Original Voice Lab speech → PRIME intent → *local-only* timer start.

    TTS is produced before the in-memory timer is created, so a failed
    spoken acknowledgement cannot leave a silently running timer.
    """
    if type(explicit_synthetic_run) is not bool or not explicit_synthetic_run:
        raise LocalTimerHold("explicit_synthetic_local_timer_run_required")
    if type(timer) is not InMemoryTimerPilot:
        raise LocalTimerHold("original_in_process_synthetic_timer_required")
    if type(pcm16) is not bytes or not 320 <= len(pcm16) <= MAX_AUDIO_BYTES or len(pcm16) % 2:
        raise LocalTimerHold("bounded_synthetic_voice_pcm_required")
    if not callable(getattr(stt, "transcribe", None)) or not callable(getattr(tts, "synthesize", None)):
        raise LocalTimerHold("original_voice_lab_stt_tts_required")
    try:
        speech = stt.transcribe(pcm16)
    except (ValueError, RuntimeError, OSError, TimeoutError):
        return {
            "status": "ORIGINAL_STT_FAILED_HOLD",
            "timer_created": False, "real_reminder_delivered": False,
            "execution_authority": "none",
        }
    intent = classify_synthetic_spoken_timer(speech)
    if intent["status"] != "FICTIONAL_TIMER_INTENT_RECOGNISED":
        return {
            "status": intent["status"], "timer_created": False,
            "real_reminder_delivered": False, "execution_authority": "none",
        }
    # Existing original AGI is unchanged and does not grant live timer use.
    review = review_capability_request({
        "agent_id": "prime_local_timer_research_pilot",
        "capability": "__unregistered_timer_service__",
        "authority_mode": "OBSERVE", "approval_present": False,
        "granted_capabilities": [],
    })
    if review["permitted"] is True:
        raise LocalTimerHold("original_live_timer_permission_must_remain_closed")
    seconds = intent["requested_seconds"]
    ack = f"Sandbox timer for {seconds} seconds started locally. No reminder was sent to a real device."
    try:
        audio = tts.synthesize(ack)
    except (ValueError, RuntimeError, OSError, TimeoutError):
        return {
            "status": "ORIGINAL_TTS_FAILED_HOLD", "timer_created": False,
            "real_reminder_delivered": False, "execution_authority": "none",
        }
    if type(audio) is not bytes or not 320 <= len(audio) <= MAX_SPOKEN_RESPONSE_BYTES or len(audio) % 2:
        return {
            "status": "ORIGINAL_TTS_AUDIO_INVALID_HOLD", "timer_created": False,
            "real_reminder_delivered": False, "execution_authority": "none",
        }
    created = timer.create(
        request_key=request_key, duration_seconds=seconds,
        explicit_synthetic_run=True,
    )
    return {
        "schema_version": "empire.prime.original_voice_local_timer_pilot.v1",
        "mode": "SYNTHETIC_LOCAL_ONLY",
        "status": "IN_MEMORY_TIMER_STARTED_NOT_REAL_DELIVERY",
        "in_memory_timer_state": created["state"],
        "synthetic_timer_seconds": seconds,
        "spoken_ack_pcm16_bytes": len(audio),
        "real_device_notified": False,
        "real_reminder_delivered": False,
        "original_empiredb_writes": False,
        "execution_authority": "test_local_memory_only",
    }
