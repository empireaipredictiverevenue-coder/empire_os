#!/usr/bin/env python3
"""Standalone FastEmbed worker. Do NOT import empire_os or touch its runtime.

Only used by explicitly opted-in, one-shot, offline semantic research.
Reads bounded JSON on stdin and emits numerical vectors to stdout.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ValueError("one explicit model cache directory required")
        cache = Path(sys.argv[1]).expanduser().resolve(strict=True)
        if not cache.is_dir():
            raise ValueError("missing model cache directory")
        raw = sys.stdin.buffer.read(160_001)
        if len(raw) > 160_000:
            raise ValueError("input exceeds worker size limit")
        data = json.loads(raw)
        texts = data.get("texts")
        if not isinstance(texts, list) or not 1 <= len(texts) <= 100:
            raise ValueError("bounded nonempty texts array required")
        if any(not isinstance(t, str) or not t.strip() or len(t) > 1500 for t in texts):
            raise ValueError("all input strings must be 1..1500 characters")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from fastembed import TextEmbedding

        model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5", cache_dir=str(cache),
            threads=2, local_files_only=True,
        )
        vectors = [[float(x) for x in vector]
                   for vector in model.embed(texts, batch_size=16, parallel=None)]
        if len(vectors) != len(texts) or any(
            len(row) != 384 or not all(math.isfinite(x) for x in row)
            for row in vectors
        ):
            raise ValueError("local embedding model returned unexpected vectors")
        print(json.dumps({"vectors": vectors}, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "UNAVAILABLE", "reason": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
