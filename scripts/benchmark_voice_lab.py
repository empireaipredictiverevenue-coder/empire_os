#!/usr/bin/env python3
"""Empire Voice Lab latency/accuracy benchmark.

No network APIs, calls, outreach, billing or revenue mutations.
Measures cold/warm native speech latency and compares two local STT paths.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import time

import numpy as np
import sherpa_onnx

from empire_os.voice_lab import (
    MODEL_ROOT,
    SherpaKokoroTTS,
    SherpaWhisperSTT,
    VoiceLabConfig,
)


NEGATION_PHRASE = (
    "Empire Voice Lab local speech readiness test. "
    "No external voice vendor is being used."
)
SHORT_REPLY = (
    "Thanks. I can send the one-page evidence brief. "
    "Who handles growth for your business?"
)
STREAM_DIR = (
    MODEL_ROOT
    / "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
)


def seconds(fn):
    start = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - start


def zipformer_ready() -> bool:
    files = (
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
        "tokens.txt",
    )
    return all((STREAM_DIR / name).is_file() for name in files)


def zipformer_transcribe(pcm16: bytes, threads: int) -> str:
    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(STREAM_DIR / "tokens.txt"),
        encoder=str(
            STREAM_DIR / "encoder-epoch-99-avg-1.int8.onnx"
        ),
        decoder=str(
            STREAM_DIR / "decoder-epoch-99-avg-1.onnx"
        ),
        joiner=str(
            STREAM_DIR / "joiner-epoch-99-avg-1.int8.onnx"
        ),
        num_threads=threads,
        sample_rate=16000,
        decoding_method="greedy_search",
        provider="cpu",
    )
    audio = (
        np.frombuffer(pcm16, dtype="<i2")
        .astype(np.float32)
        / 32768.0
    )
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, audio)
    stream.input_finished()
    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)
    return str(recognizer.get_result(stream).text or "").strip()


def benchmark_threads(threads: int) -> dict:
    cfg = VoiceLabConfig(num_threads=threads)
    tts = SherpaKokoroTTS(cfg)

    neg_pcm, tts_cold = seconds(
        lambda: tts.synthesize(NEGATION_PHRASE)
    )
    _warm_pcm, tts_warm = seconds(
        lambda: tts.synthesize(SHORT_REPLY)
    )
    _warm_pcm2, tts_warm2 = seconds(
        lambda: tts.synthesize(SHORT_REPLY)
    )

    whisper = SherpaWhisperSTT(cfg)
    whisper_text, whisper_cold = seconds(
        lambda: whisper.transcribe(neg_pcm)
    )
    whisper_text2, whisper_warm = seconds(
        lambda: whisper.transcribe(neg_pcm)
    )

    zip_text = None
    zip_seconds = None
    if zipformer_ready():
        zip_text, zip_seconds = seconds(
            lambda: zipformer_transcribe(neg_pcm, threads)
        )

    return {
        "threads": threads,
        "tts_cold_seconds": round(tts_cold, 3),
        "tts_warm_seconds": round(tts_warm, 3),
        "tts_warm_repeat_seconds": round(tts_warm2, 3),
        "whisper_cold_seconds": round(whisper_cold, 3),
        "whisper_warm_seconds": round(whisper_warm, 3),
        "whisper_transcript": whisper_text,
        "whisper_repeat_transcript": whisper_text2,
        "zipformer_seconds": (
            round(zip_seconds, 3)
            if zip_seconds is not None else None
        ),
        "zipformer_transcript": zip_text,
        "expected_negation_present_whisper": (
            "no external" in whisper_text.lower()
        ),
        "expected_negation_present_zipformer": (
            bool(zip_text)
            and "no external" in zip_text.lower()
        ),
        "pcm_bytes": len(neg_pcm),
    }


def main() -> int:
    generate_sig = ""
    try:
        generate_sig = str(
            inspect.signature(sherpa_onnx.OfflineTts.generate)
        )
    except Exception as exc:
        generate_sig = f"unavailable:{type(exc).__name__}"

    rows = [benchmark_threads(n) for n in (1, 2, 4, 8)]
    viable = [
        row for row in rows
        if row["tts_warm_repeat_seconds"] > 0
    ]
    best = min(
        viable,
        key=lambda row: row["tts_warm_repeat_seconds"],
    )

    print(json.dumps({
        "schema_version": "empire.voice_benchmark.v1",
        "ok": True,
        "speech_vendor": None,
        "live_call_placed": False,
        "outbound_mutation": False,
        "zipformer_model_ready": zipformer_ready(),
        "offline_tts_generate_signature": generate_sig,
        "benchmarks": rows,
        "best_tts_threads": best["threads"],
        "best_warm_tts_seconds": best["tts_warm_repeat_seconds"],
        "accuracy_gate": {
            "phrase": NEGATION_PHRASE,
            "requires_negation_preserved": True,
        },
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
