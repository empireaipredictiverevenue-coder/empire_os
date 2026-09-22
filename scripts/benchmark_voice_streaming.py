#!/usr/bin/env python3
"""Focused Empire Voice Lab first-audio benchmark.

Measures the latency that matters for a live phone conversation: how long
Kokoro takes to emit the first playable PCM chunk through sherpa-onnx's
generation callback. No calls, outreach, billing, or revenue mutations.
"""
from __future__ import annotations

import json
import os
import time

from empire_os.voice_lab import SherpaKokoroTTS, VoiceLabConfig


TEXT = (
    "Thanks. "
    "I can send the one-page evidence brief. "
    "Who handles growth for your business?"
)


def main() -> int:
    threads = max(
        1,
        int(os.getenv("EMPIRE_VOICE_NUM_THREADS", "4")),
    )
    cfg = VoiceLabConfig(num_threads=threads)
    tts = SherpaKokoroTTS(cfg)

    started = time.perf_counter()
    first_chunk_at: float | None = None
    chunk_times: list[float] = []
    chunk_bytes: list[int] = []

    def on_chunk(pcm: bytes, _progress: float) -> None:
        nonlocal first_chunk_at
        now = time.perf_counter()
        elapsed = now - started
        if first_chunk_at is None:
            first_chunk_at = elapsed
        chunk_times.append(round(elapsed, 3))
        chunk_bytes.append(len(pcm))
        print(
            "[voice-stream] "
            f"chunk={len(chunk_times)} "
            f"at={elapsed:.3f}s "
            f"bytes={len(pcm)}",
            flush=True,
        )

    print(
        "[voice-stream] starting "
        f"threads={threads} "
        f"cpu_count={os.cpu_count()} "
        f"loadavg={tuple(round(v, 2) for v in os.getloadavg())}",
        flush=True,
    )
    stats = tts.stream(TEXT, on_chunk)
    total = time.perf_counter() - started

    audio_seconds = sum(chunk_bytes) / 2 / cfg.output_rate
    first_audio = (
        round(first_chunk_at, 3)
        if first_chunk_at is not None else None
    )
    result = {
        "schema_version": "empire.voice_stream_benchmark.v1",
        "ok": bool(chunk_bytes),
        "speech_vendor": None,
        "live_call_placed": False,
        "outbound_mutation": False,
        "threads": threads,
        "first_chunk_seconds": first_audio,
        "total_generation_seconds": round(total, 3),
        "audio_seconds": round(audio_seconds, 3),
        "total_rtf": (
            round(total / audio_seconds, 3)
            if audio_seconds > 0 else None
        ),
        "chunk_count": len(chunk_bytes),
        "chunk_emit_seconds": chunk_times,
        "chunk_bytes": chunk_bytes,
        "stream_stats": stats,
        "host": {
            "cpu_count": os.cpu_count(),
            "loadavg": [
                round(value, 3) for value in os.getloadavg()
            ],
        },
        "text": TEXT,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if chunk_bytes else 1


if __name__ == "__main__":
    raise SystemExit(main())
