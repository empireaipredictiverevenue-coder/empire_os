#!/usr/bin/env python3
"""One-shot offline original Voice Lab STT/TTS ↔ PRIME timer-intent rehearsal.

This uses a locally synthesized FICTIONAL request, never a microphone, real
person, cloud vendor, scheduler, contact, trade, payment or production DB.
An OS-level timeout should be supplied externally for the potentially heavy
speech models. No PCM or private transcripts are persisted to disk.
"""
from __future__ import annotations

import json
from time import monotonic

from empire_os.voice_lab import VoiceLabConfig, SherpaKokoroTTS, SherpaWhisperSTT
from empire_os.prime_flagship_voice_task_rehearsal import (
    review_fictional_voice_task, founder_voice_task_status,
)

FICTIONAL_INPUT = "Set a timer for two minutes."


def main() -> int:
    config = VoiceLabConfig.from_env()
    tts = SherpaKokoroTTS(config)
    stt = SherpaWhisperSTT(config)
    t0 = monotonic()
    packet = {
        "schema_version": "empire.prime.original_voice_audio_roundtrip_observation.v1",
        "mode": "OFFLINE_SYNTHETIC",
        "speech_backend": "original_sherpa_whisper_and_kokoro",
        "fictional_input_only": True,
        "input_audio_bytes": 0,
        "local_stt_elapsed_seconds": None,
        "local_tts_elapsed_seconds": None,
        "voice_task": founder_voice_task_status(None),
        "original_speech_engine_end_to_end_pass": False,
        "real_user_task_scheduled": False,
        "original_empiredb_writes": False,
        "external_voice_call_placed": False,
        "actual_revenue_cents": None,
        "execution_authority": "none",
    }
    try:
        spoken_input = tts.synthesize(FICTIONAL_INPUT)
        packet["input_audio_bytes"] = len(spoken_input)
        packet["local_tts_elapsed_seconds"] = round(monotonic() - t0, 3)
        if len(spoken_input) < 320 or len(spoken_input) > 960000:
            raise ValueError("synthetic_input_audio_out_of_bounds")
        stt_started = monotonic()
        class MeasuredSTT:
            def transcribe(self, pcm16: bytes) -> str:
                answer = stt.transcribe(pcm16)
                packet["local_stt_elapsed_seconds"] = round(monotonic() - stt_started, 3)
                return answer
        result = review_fictional_voice_task(
            pcm16=spoken_input, stt=MeasuredSTT(), tts=tts,
            include_fictional_audio=False,
        )
        packet["voice_task"] = founder_voice_task_status(result)
        packet["original_speech_engine_end_to_end_pass"] = (
            result["status"] == "FICTIONAL_SPOKEN_ACK_AUDIO_VERIFIED_NOT_SCHEDULED"
            and result["synthetic_requested_timer_seconds"] == 120
        )
    except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
        packet["held_reason_code"] = "ORIGINAL_OFFLINE_SPEECH_ERROR_" + type(exc).__name__.upper()
    packet["elapsed_seconds"] = round(monotonic() - t0, 3)
    print(json.dumps(packet, sort_keys=True, indent=2))
    return 0 if packet["original_speech_engine_end_to_end_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
