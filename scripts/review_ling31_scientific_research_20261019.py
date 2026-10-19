#!/usr/bin/env python3
"""Ling 3.1 / Scientific Agent integration check, read-only by default.

--probe-free-zen makes ONE fixed public PONG request to the documented free
model slug using the existing key. Paid model routes are never considered.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from empire_os.ling31_research_readiness import (
    probe_ling31_free, review_ling31_free_readiness,
    scientific_research_protocol,
)
from empire_os.model_registry import ModelRegistry
from empire_os.revenue_stream_mining import build_revenue_stream_mining


def main() -> int:
    parser = argparse.ArgumentParser(description="Scientific Ling 3.1 readiness")
    parser.add_argument("--probe-free-zen", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    registry = ModelRegistry(str(repo_root/"config/model_registry.json"))
    runtime = build_revenue_stream_mining(Path("/srv/empire_os"))
    result = {
        "ling": review_ling31_free_readiness(registry=registry),
        "scientific_protocol": scientific_research_protocol(runtime),
    }
    if args.probe_free_zen:
        result["free_model_probe"] = probe_ling31_free()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
