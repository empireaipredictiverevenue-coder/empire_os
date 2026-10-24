#!/usr/bin/env python3
"""Real offline Kokoro/Whisper→PRIME local 2-second timer expiry experiment.

Synthetic prompt, no mic, phone, email, real user, notification channel,
external scheduler, persistence, model generation or production mutation.
The only delivered item is one in-process event to an in-memory test sink.
"""
from __future__ import annotations

import json
from time import monotonic, sleep

from empire_os.voice_lab import VoiceLabConfig, SherpaKokoroTTS, SherpaWhisperSTT
from empire_os.prime_flagship_local_timer_pilot import (
    InMemorySink, InMemoryTimerPilot, rehearse_voice_to_local_timer,
)

FICTIONAL_REQUEST = "Set a timer for two seconds."


def main() -> int:
    started = monotonic()
    config = VoiceLabConfig.from_env()
    voice = SherpaKokoroTTS(config)
    recognizer = SherpaWhisperSTT(config)
    sink = InMemorySink()
    timer = InMemoryTimerPilot(sink=sink)
    report = {
        "schema_version": "empire.prime.original_actual_local_timer_expiry.v1",
        "mode": "OFFLINE_SYNTHETIC",
        "original_voice_lab_used": True,
        "fictional_spoken_input_only": True,
        "actual_timer_notification_to_user": False,
        "original_empiredb_writes": False,
        "outbound_sent": False,
        "real_user_notification_sent": False,
        "execution_authority": "test_local_memory_only",
        "expiry_observed_in_process": False,
        "one_local_receipt_verified": False,
        "replay_suppressed": False,
    }
    try:
        input_pcm = voice.synthesize(FICTIONAL_REQUEST)
        report["fictional_input_audio_bytes"] = len(input_pcm)
        report["preparation_seconds"] = round(monotonic() - started, 3)
        outcome = rehearse_voice_to_local_timer(
            pcm16=input_pcm, stt=recognizer, tts=voice,
            timer=timer, request_key="sim_fictional_voice_two_seconds",
            explicit_synthetic_run=True,
        )
        report["voice_to_timer_status"] = outcome["status"]
        if outcome.get("status") != "IN_MEMORY_TIMER_STARTED_NOT_REAL_DELIVERY":
            report["status"] = "VOICE_INTENT_OR_SYNTHETIC_TTS_HOLD"
        else:
            report["recognized_timer_seconds"] = outcome["synthetic_timer_seconds"]
            report["synthetic_spoken_ack_bytes"] = outcome["spoken_ack_pcm16_bytes"]
            report["observed_not_due_before_deadline"] = (
                not timer.poll_due(explicit_synthetic_run=True)
            )
            sleep(2.1)  # actual finite in-process timer, not background automation
            receipts = timer.poll_due(explicit_synthetic_run=True)
            report["expiry_observed_in_process"] = (
                len(receipts) == 1
                and receipts[0]["state"] == "LOCAL_SINK_ACKNOWLEDGED_ONLY"
            )
            report["one_local_receipt_verified"] = (
                len(sink.events) == 1
                and sink.events[0]["kind"] == "LOCAL_TIMER_EXPIRED"
                and sink.events[0]["external_delivery"] is False
                and receipts[0]["local_sink_receipt"] is not None
            )
            report["replay_suppressed"] = (
                not timer.poll_due(explicit_synthetic_run=True)
                and len(sink.events) == 1
            )
            report["status"] = (
                "REAL_LOCAL_SYNTHETIC_TIMER_EXPIRED_ONCE"
                if (report["expiry_observed_in_process"]
                    and report["one_local_receipt_verified"]
                    and report["replay_suppressed"]
                    and report["observed_not_due_before_deadline"]
                    and report["recognized_timer_seconds"] == 2)
                else "LOCAL_TIMER_EXPIRY_INVARIANT_HOLD"
            )
    except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
        report["status"] = "OFFLINE_SPEECH_OR_TIMER_ERROR_" + type(exc).__name__.upper()
    report["elapsed_seconds"] = round(monotonic() - started, 3)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] == "REAL_LOCAL_SYNTHETIC_TIMER_EXPIRED_ONCE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
