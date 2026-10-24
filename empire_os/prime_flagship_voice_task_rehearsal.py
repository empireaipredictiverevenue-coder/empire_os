"""Offline original EmpireOS Voice Lab → PRIME task → Voice Lab rehearsal.

Uses self-hosted speech recognition/synthesis contracts; all example speech
must be fictional and explicitly authorised. No Vonage, Supabase, microphone,
scheduler, calendar, notification, model generation, production or external
tool execution. A synthetically acknowledged timer is NOT a scheduled timer.

This is an isolated first-step evidence test for the flagship end-to-end flow.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from empire_os.agi_capabilities import review_capability_request
from empire_os.decision_judge import OPT_OUT_PATTERNS, NEGATIVE_PATTERNS

SCHEMA = "empire.prime.flagship_voice_task_rehearsal.v1"
MAX_AUDIO_BYTES = 960000  # 30 s @ 16 kHz mono PCM16
MAX_TEXT_CHARS = 220
MAX_SPOKEN_RESPONSE_BYTES = 960000
VOICE_STATUS_CODES = frozenset({
    "FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED",
    "AUDIO_TRANSCRIPT_INVALID_HOLD", "STOP_OR_EMERGENCY_NO_AUTOMATION_HOLD",
    "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD", "UNKNOWN_OR_AMBIGUOUS_TIMER_REQUEST",
    "UNSUPPORTED_EXTRA_CLAUSE_HOLD", "TIMER_DURATION_OUT_OF_BOUNDS_HOLD",
    "ORIGINAL_STT_FAILED_HOLD", "ORIGINAL_TTS_FAILED_HOLD",
    "INVALID_SYNTHETIC_SPEECH_AUDIO_HOLD",
})
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30,
}
TIMER_PATTERN = re.compile(
    r"\b(?:set|start|create)\s+(?:a\s+)?timer\s+(?:for\s+)?"
    r"(?P<number>\d{1,3}|zero|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|fifteen|twenty|thirty)\s*(?P<unit>seconds?|minutes?)\b",
    re.IGNORECASE,
)
UNTRUSTED_CONTROL = re.compile(
    r"(?:\b(?:transfer|send|pay|charge|buy|trade|delete|deploy|"
    r"call|text|email|contact|unlock|start the car|turn on the gas)\b|"
    r"\b(?:password|api key|bank account|credit card)\b|"
    r"https?://|www\.|@|[<>\{\}]|"
    r"\b(?:ignore instructions|system prompt|jailbreak|override permissions)\b)",
    re.IGNORECASE,
)
EMERGENCY = re.compile(r"\b(?:emergency|ambulance|fire|police|help me i am hurt)\b",re.I)


class Recognizer(Protocol):
    def transcribe(self, pcm16: bytes) -> str: ...


class Speaker(Protocol):
    def synthesize(self, text: str) -> bytes: ...


@dataclass(frozen=True)
class VoiceRehearsalBudget:
    input_audio_max_bytes: int = MAX_AUDIO_BYTES
    output_audio_max_bytes: int = MAX_SPOKEN_RESPONSE_BYTES
    max_duration_seconds: int = 3600

    def validate(self) -> None:
        if (type(self.input_audio_max_bytes) is not int
            or not 320 <= self.input_audio_max_bytes <= MAX_AUDIO_BYTES
            or type(self.output_audio_max_bytes) is not int
            or not 320 <= self.output_audio_max_bytes <= MAX_SPOKEN_RESPONSE_BYTES
            or type(self.max_duration_seconds) is not int
            or not 1 <= self.max_duration_seconds <= 3600):
            raise ValueError("bounded_flagship_offline_audio_contract_required")


def classify_synthetic_spoken_timer(text: str, *, maximum_seconds: int = 3600) -> dict[str, Any]:
    """Exact timer-intent preview; never a live tool capability."""
    if (type(text) is not str or not 1 <= len(text) <= MAX_TEXT_CHARS
        or "\n" in text or "\r" in text or "\x00" in text):
        return {"status": "AUDIO_TRANSCRIPT_INVALID_HOLD", "requested_seconds": None}
    current = text.strip()
    if (EMERGENCY.search(current) or any(re.search(p,current,re.I) for p in OPT_OUT_PATTERNS)
        or any(re.search(p,current,re.I) for p in NEGATIVE_PATTERNS)):
        return {"status": "STOP_OR_EMERGENCY_NO_AUTOMATION_HOLD", "requested_seconds": None}
    if UNTRUSTED_CONTROL.search(current):
        return {"status": "UNRELATED_OR_HIGH_RISK_COMMAND_HOLD", "requested_seconds": None}
    matches = list(TIMER_PATTERN.finditer(current))
    if len(matches) != 1:
        return {"status": "UNKNOWN_OR_AMBIGUOUS_TIMER_REQUEST", "requested_seconds": None}
    match = matches[0]
    if current[:match.start()].strip(" ,.!?").lower() not in (
        "", "please", "hey empire", "empire", "empire ai", "could you please"
    ):
        return {"status": "UNSUPPORTED_EXTRA_CLAUSE_HOLD", "requested_seconds": None}
    if current[match.end():].strip(" ,.!?").lower() not in ("", "please", "thank you", "thanks"):
        return {"status": "UNSUPPORTED_EXTRA_CLAUSE_HOLD", "requested_seconds": None}
    quantity = match.group("number").lower()
    value = int(quantity) if quantity.isdigit() else NUMBER_WORDS[quantity]
    seconds = value * (60 if match.group("unit").lower().startswith("minute") else 1)
    if not 1 <= seconds <= maximum_seconds:
        return {"status": "TIMER_DURATION_OUT_OF_BOUNDS_HOLD", "requested_seconds": None}
    return {"status": "FICTIONAL_TIMER_INTENT_RECOGNISED", "requested_seconds": seconds}


def review_fictional_voice_task(
    *, pcm16: bytes, stt: Recognizer, tts: Speaker,
    budget: VoiceRehearsalBudget = VoiceRehearsalBudget(),
    include_fictional_audio: bool = False,
) -> dict[str, Any]:
    """Run a complete *simulated* voice path with actual injected speech engines.

    This boundary does not grant a timer or voice device permission. All speech
    text remains in memory; founder status never includes raw transcript/audio.
    """
    budget.validate()
    if type(pcm16) is not bytes or not 320 <= len(pcm16) <= budget.input_audio_max_bytes or len(pcm16) % 2:
        raise ValueError("bounded_16khz_pcm16_fictional_audio_required")
    if (type(include_fictional_audio) is not bool
        or not callable(getattr(stt, "transcribe", None))
        or not callable(getattr(tts, "synthesize", None))):
        raise ValueError("existing_original_speech_engines_required")
    try:
        original = stt.transcribe(pcm16)
    except (ValueError, RuntimeError, OSError, TimeoutError):
        return _report("ORIGINAL_STT_FAILED_HOLD", None, None, 0, False, None)
    classification = classify_synthetic_spoken_timer(
        original, maximum_seconds=budget.max_duration_seconds,
    )
    status = classification["status"]
    seconds = classification["requested_seconds"]
    if seconds is None:
        return _report(status, None, None, 0, False, None)

    # The existing AGI capability registry has no actual timer scheduler
    # attached. A voice utterance is NOT evidence of permission to schedule.
    original_policy = review_capability_request({
        "agent_id": "prime_original_voice_task_rehearsal",
        "capability": "__unregistered_timer_service__",
        "authority_mode": "OBSERVE",
        "approval_present": False,
        "granted_capabilities": [],
    })
    if original_policy["permitted"] is True:
        raise RuntimeError("unregistered_original_timer_must_never_be_authorized")
    answer = (
        f"I heard a request for a {seconds} second timer. "
        "This is a demonstration. No timer has been scheduled."
    )
    try:
        audio = tts.synthesize(answer)
    except (ValueError, RuntimeError, OSError, TimeoutError):
        return _report("ORIGINAL_TTS_FAILED_HOLD", seconds, answer, 0, False, None)
    if (type(audio) is not bytes or len(audio) < 320 or len(audio) % 2
        or len(audio) > budget.output_audio_max_bytes):
        return _report("INVALID_SYNTHETIC_SPEECH_AUDIO_HOLD", seconds, answer, 0, False, None)
    return _report("FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED",
                   seconds, answer, len(audio), True, audio if include_fictional_audio else None)


def _report(
    status: str, seconds: int | None, text: str | None, audio_bytes: int,
    audio_verified: bool, audio: bytes | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "status": status,
        "synthetic_requested_timer_seconds": seconds,
        "approved_original_timer_executor_connected": False,
        "spoken_ack_text_is_fictional": text,
        "synthetic_spoken_output_bytes": audio_bytes,
        "original_tts_audio_bytes_verified": audio_verified,
        "fictional_spoken_pcm16_bytes": audio,
        "asr_text_not_exposed_by_this_report": True,
        "audio_contains_no_real_person_claim": True,
        "timer_scheduled": False,
        "notification_delivered": False,
        "voice_call_placed": False,
        "recording_persisted": False,
        "real_customer_data_used": False,
        "original_empiredb_writes": False,
        "payment_executed": False,
        "outbound_sent": False,
        "model_weights_changed": False,
        "execution_authority": "none",
    }


def founder_voice_task_status(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {
            "schema_version": "empire.prime.founder_voice_task_rehearsal.v1",
            "mode": "SIMULATION", "status": "NOT_RUN",
            "actual_timer_scheduled": False, "execution_authority": "none",
        }
    if (type(value) is not dict or value.get("schema_version") != SCHEMA
        or set(value) != {
            "schema_version", "mode", "status", "synthetic_requested_timer_seconds",
            "approved_original_timer_executor_connected", "spoken_ack_text_is_fictional",
            "synthetic_spoken_output_bytes", "original_tts_audio_bytes_verified",
            "fictional_spoken_pcm16_bytes", "asr_text_not_exposed_by_this_report",
            "audio_contains_no_real_person_claim", "timer_scheduled",
            "notification_delivered", "voice_call_placed", "recording_persisted",
            "real_customer_data_used", "original_empiredb_writes",
            "payment_executed", "outbound_sent", "model_weights_changed",
            "execution_authority",
        }
        or value.get("status") not in VOICE_STATUS_CODES
        or type(value.get("synthetic_spoken_output_bytes")) is not int
        or not 0 <= value["synthetic_spoken_output_bytes"] <= MAX_SPOKEN_RESPONSE_BYTES
        or type(value.get("original_tts_audio_bytes_verified")) is not bool
        or (value["original_tts_audio_bytes_verified"] is True) is not
            (value["status"] == "FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED")
        or (value["synthetic_requested_timer_seconds"] is not None and
            (type(value["synthetic_requested_timer_seconds"]) is not int or
             not 1 <= value["synthetic_requested_timer_seconds"] <= 3600))
        or value.get("mode") != "SIMULATION"
        or value.get("execution_authority") != "none"
        or value.get("timer_scheduled") is not False
        or value.get("notification_delivered") is not False
        or value.get("voice_call_placed") is not False
        or value.get("real_customer_data_used") is not False
        or value.get("recording_persisted") is not False
        or value.get("original_empiredb_writes") is not False
        or value.get("payment_executed") is not False
        or value.get("outbound_sent") is not False
        or value.get("model_weights_changed") is not False
        or value.get("approved_original_timer_executor_connected") is not False
        or value.get("asr_text_not_exposed_by_this_report") is not True
        or value.get("audio_contains_no_real_person_claim") is not True
        or value.get("fictional_spoken_pcm16_bytes") is not None):
        raise ValueError("forged_flagship_voice_task_authority")
    return {
        "schema_version": "empire.prime.founder_voice_task_rehearsal.v1",
        "mode": "SIMULATION",
        "status": value["status"],
        "synthetic_timer_duration_seconds": value["synthetic_requested_timer_seconds"],
        "synthetic_spoken_audio_bytes": value["synthetic_spoken_output_bytes"],
        "actual_timer_scheduled": False,
        "independently_verified_consented_voice_task": False,
        "execution_authority": "none",
    }
