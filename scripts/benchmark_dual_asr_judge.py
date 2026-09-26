#!/usr/bin/env python3
"""Focused dual-ASR + Empire Decision Judge benchmark.

No network APIs, no calls, no outreach, no billing, no revenue mutation.
Uses the local TTS only to create a repeatable speech sample, then measures
Whisper, Zipformer and the typed Decision Judge together.
"""
from __future__ import annotations

import json
import time

from empire_os.decision_judge import EmpireDecisionJudge, TranscriptCandidate
from empire_os.voice_lab import (
    SherpaKokoroTTS,
    SherpaWhisperSTT,
    SherpaZipformerVerifierSTT,
    VoiceLabConfig,
)


TEXT = (
    "Empire Voice Lab local speech readiness test. "
    "No external voice vendor is being used."
)


def timed(fn):
    started = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - started


def main() -> int:
    cfg = VoiceLabConfig(num_threads=4)
    if not SherpaZipformerVerifierSTT.ready(cfg):
        raise SystemExit("Zipformer verifier model is not ready")

    tts = SherpaKokoroTTS(cfg)
    whisper = SherpaWhisperSTT(cfg)
    zipformer = SherpaZipformerVerifierSTT(cfg)
    judge = EmpireDecisionJudge()

    pcm, tts_seconds = timed(lambda: tts.synthesize(TEXT))
    whisper_text, whisper_seconds = timed(
        lambda: whisper.transcribe(pcm)
    )
    zip_text, zip_seconds = timed(
        lambda: zipformer.transcribe(pcm)
    )
    decision, judge_seconds = timed(
        lambda: judge.judge_candidates([
            TranscriptCandidate(
                source="sherpa_whisper",
                text=whisper_text,
            ),
            TranscriptCandidate(
                source="sherpa_zipformer",
                text=zip_text,
            ),
        ])
    )

    result = {
        "schema_version": "empire.dual_asr_judge_benchmark.v1",
        "ok": True,
        "live_call_placed": False,
        "outbound_mutation": False,
        "speech_vendor": None,
        "text": TEXT,
        "threads": 4,
        "tts_seconds": round(tts_seconds, 3),
        "whisper_seconds": round(whisper_seconds, 3),
        "zipformer_seconds": round(zip_seconds, 3),
        "judge_seconds": round(judge_seconds, 6),
        "decision_path_seconds": round(
            whisper_seconds + zip_seconds + judge_seconds,
            3,
        ),
        "whisper_transcript": whisper_text,
        "zipformer_transcript": zip_text,
        "decision": decision.to_dict(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
