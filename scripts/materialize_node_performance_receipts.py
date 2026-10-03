#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from empire_os.node_performance_receipts import (
    load_benchmark_receipts,
    receipt_snapshot,
)


DEFAULT_SOURCE = Path(
    "runtime/hybrid_compute/"
    "local_escalation_v2_latest.json"
)

DEFAULT_OUTPUT = Path(
    "runtime/hybrid_compute/"
    "node_performance_receipts_latest.json"
)


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            text=True,
        ).strip()
    except Exception:
        return None


def atomic_write(
    path: Path,
    payload: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        path.suffix + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
    )

    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)

    receipts = load_benchmark_receipts(
        source,
        source_commit=git_commit(),
    )

    payload = receipt_snapshot(
        receipts,
        source_path=str(source),
    )

    atomic_write(
        output,
        payload,
    )

    print(
        json.dumps(
            {
                "output": str(output),
                "receipt_count":
                    payload["receipt_count"],
                "node_ids":
                    sorted(receipts),
                "economic_memory_verified":
                    False,
                "production_authority":
                    False,
                "route_changed":
                    False,
                "execution_authority":
                    "none",
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
