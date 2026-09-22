#!/usr/bin/env python3
"""Compare Empire Voice Lab TTS candidates without changing production.

Measures model load time plus cold/warm callback first-audio latency, total
generation time, generated audio duration, and real-time factor.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Callable

import numpy as np
import sherpa_onnx


ROOT = Path(
    os.getenv(
        "EMPIRE_VOICE_MODEL_ROOT",
        "/srv/empire_os/runtime/models/voice_lab",
    )
)
TEXT = (
    "Thanks. "
    "I can send the one-page evidence brief. "
    "Who handles growth for your business?"
)
THREADS = max(1, int(os.getenv("EMPIRE_VOICE_NUM_THREADS", "4")))


def require(root: Path, name: str) -> str:
    path = root / name
    if not path.is_file() and not path.is_dir():
        raise FileNotFoundError(str(path))
    return str(path)


def kokoro_factory(root: Path, model_name: str):
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=require(root, model_name),
                voices=require(root, "voices.bin"),
                tokens=require(root, "tokens.txt"),
                data_dir=require(root, "espeak-ng-data"),
                lexicon="",
            ),
            provider="cpu",
            debug=False,
            num_threads=THREADS,
        ),
        max_num_sentences=1,
    )
    if not cfg.validate():
        raise RuntimeError(f"invalid Kokoro config: {root}")
    return sherpa_onnx.OfflineTts(cfg), 10


def kitten_factory(root: Path):
    kitten_cls = getattr(
        sherpa_onnx,
        "OfflineTtsKittenModelConfig",
        None,
    )
    if kitten_cls is None:
        raise RuntimeError(
            "installed sherpa-onnx lacks KittenTTS Python bindings"
        )
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kitten=kitten_cls(
                model=require(root, "model.int8.onnx"),
                voices=require(root, "voices.bin"),
                tokens=require(root, "tokens.txt"),
                data_dir=require(root, "espeak-ng-data"),
            ),
            provider="cpu",
            debug=False,
            num_threads=THREADS,
        ),
        max_num_sentences=1,
    )
    if not cfg.validate():
        raise RuntimeError(f"invalid Kitten config: {root}")
    return sherpa_onnx.OfflineTts(cfg), 0


def generation_config(sid: int):
    cfg = sherpa_onnx.GenerationConfig()
    cfg.sid = sid
    cfg.speed = 1.0
    cfg.silence_scale = 0.2
    return cfg


def one_run(tts, sid: int) -> dict:
    started = time.perf_counter()
    first_audio: float | None = None
    callback_samples = 0
    callback_count = 0

    def callback(samples: np.ndarray, _progress: float) -> int:
        nonlocal first_audio, callback_samples, callback_count
        now = time.perf_counter()
        if first_audio is None:
            first_audio = now - started
        callback_count += 1
        callback_samples += int(len(samples))
        return 1

    audio = tts.generate(
        TEXT,
        generation_config(sid),
        callback,
    )
    total = time.perf_counter() - started
    sample_rate = int(
        audio.sample_rate
        or getattr(tts, "sample_rate", 0)
        or 24000
    )
    samples = int(len(audio.samples))
    audio_seconds = samples / sample_rate if sample_rate else 0.0
    return {
        "first_chunk_seconds": (
            round(first_audio, 3)
            if first_audio is not None
            else None
        ),
        "total_generation_seconds": round(total, 3),
        "audio_seconds": round(audio_seconds, 3),
        "rtf": (
            round(total / audio_seconds, 3)
            if audio_seconds > 0
            else None
        ),
        "callback_count": callback_count,
        "callback_samples": callback_samples,
        "sample_rate": sample_rate,
        "samples": samples,
    }


def benchmark(
    name: str,
    factory: Callable[[], tuple[object, int]],
) -> dict:
    print(f"[tts-race] {name}: load starting", flush=True)
    started = time.perf_counter()
    try:
        tts, sid = factory()
    except Exception as exc:
        print(f"[tts-race] {name}: unavailable: {exc}", flush=True)
        return {
            "name": name,
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    load_seconds = time.perf_counter() - started
    print(
        f"[tts-race] {name}: load complete "
        f"{load_seconds:.3f}s",
        flush=True,
    )

    print(f"[tts-race] {name}: cold starting", flush=True)
    cold = one_run(tts, sid)
    print(
        f"[tts-race] {name}: cold first="
        f"{cold['first_chunk_seconds']}s total="
        f"{cold['total_generation_seconds']}s",
        flush=True,
    )

    print(f"[tts-race] {name}: warm starting", flush=True)
    warm = one_run(tts, sid)
    print(
        f"[tts-race] {name}: warm first="
        f"{warm['first_chunk_seconds']}s total="
        f"{warm['total_generation_seconds']}s",
        flush=True,
    )

    return {
        "name": name,
        "available": True,
        "load_seconds": round(load_seconds, 3),
        "cold": cold,
        "warm": warm,
    }


def main() -> int:
    candidates = [
        (
            "kokoro_fp32_v0_19",
            lambda: kokoro_factory(
                ROOT / "kokoro-en-v0_19",
                "model.onnx",
            ),
        ),
        (
            "kokoro_int8_v0_19",
            lambda: kokoro_factory(
                ROOT / "kokoro-int8-en-v0_19",
                "model.int8.onnx",
            ),
        ),
        (
            "kitten_nano_int8_v0_8",
            lambda: kitten_factory(
                ROOT / "kitten-nano-en-v0_8-int8"
            ),
        ),
    ]

    print(
        "[tts-race] starting "
        f"threads={THREADS} "
        f"cpu_count={os.cpu_count()} "
        f"loadavg={tuple(round(v, 2) for v in os.getloadavg())}",
        flush=True,
    )

    results = [
        benchmark(name, factory)
        for name, factory in candidates
    ]
    available = [r for r in results if r.get("available")]
    ranked = sorted(
        available,
        key=lambda r: (
            r["warm"]["first_chunk_seconds"]
            if r["warm"]["first_chunk_seconds"] is not None
            else float("inf")
        ),
    )

    payload = {
        "schema_version": "empire.tts_candidate_benchmark.v1",
        "ok": bool(available),
        "speech_vendor": None,
        "live_call_placed": False,
        "outbound_mutation": False,
        "production_tts_changed": False,
        "threads": THREADS,
        "text": TEXT,
        "host": {
            "cpu_count": os.cpu_count(),
            "loadavg": [
                round(value, 3) for value in os.getloadavg()
            ],
        },
        "results": results,
        "ranked_by_warm_first_chunk": [
            item["name"] for item in ranked
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    return 0 if available else 1


if __name__ == "__main__":
    raise SystemExit(main())
