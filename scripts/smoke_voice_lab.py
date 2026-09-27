#!/usr/bin/env python3
"""Offline round-trip smoke test for Empire Voice Lab.

Downloads/loads the configured local STT/TTS models if they are not already
cached. It does not call Vonage, place a phone call, send outreach, or invoke
any commercial mutation.
"""
from __future__ import annotations

import json
import sys
import time

from empire_os.voice_lab import EmpireVoiceLab, VoiceLabConfig


def main() -> int:
    config = VoiceLabConfig.from_env()
    lab = EmpireVoiceLab(config)
    phrase = (
        "Empire Voice Lab local speech readiness test. "
        "No external voice vendor is being used."
    )

    t0 = time.perf_counter()
    pcm = lab.synthesize_text(phrase)
    tts_seconds = time.perf_counter() - t0
    if not pcm:
        raise RuntimeError("native TTS returned no audio")

    t1 = time.perf_counter()
    transcript = lab.stt.transcribe(pcm)
    stt_seconds = time.perf_counter() - t1
    if not transcript.strip():
        raise RuntimeError("native STT returned no transcript")

    result = {
        "ok": True,
        "engine": "empire_voice_lab",
        "speech_vendor": None,
        "tts_backend": config.tts_backend,
        "stt_backend": config.stt_backend,
        "sample_rate": config.output_rate,
        "pcm_bytes": len(pcm),
        "roundtrip_transcript": transcript,
        "tts_seconds": round(tts_seconds, 3),
        "stt_seconds": round(stt_seconds, 3),
        "live_call_placed": False,
        "outbound_mutation": False,
        "actual_revenue": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps({
                "ok": False,
                "error": f"{type(exc).__name__}:{exc}",
                "live_call_placed": False,
            }),
            file=sys.stderr,
        )
        raise SystemExit(2)
