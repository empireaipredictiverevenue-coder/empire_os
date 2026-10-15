"""Manual AGI-style Data Exchange research; no agent or tool execution.

Uses previous read-only observations and official procurement projection
to issue an auditable AGI orchestration/cognitive workstream packet.
No autonomous loop, no external model dependency, no cloud spend, no DB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_agi_bridge import review_data_exchange_agi
from empire_os.data_exchange_local_reasoning import review_local_reasoning
from empire_os.data_exchange_laya_shadow import evaluate_laya_shadow
from scripts.review_construction_history import read_bounded_snapshot

MAX_INPUT_BYTES = 512_000


def _procurement(path: Path | None) -> dict | None:
    if path is None:
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("procurement evidence not a bounded regular file")
    with path.open("r", encoding="utf-8") as stream:
        body = json.load(stream)
    if not isinstance(body, dict):
        raise ValueError("procurement evidence not an object")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", required=True, nargs="+", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--procurement", type=Path)
    parser.add_argument(
        "--local-model", action="store_true",
        help="Run one bounded first-party Qwen advisory inference, never execute actions",
    )
    parser.add_argument(
        "--laya-shadow", action="store_true",
        help="Run one existing localhost Laya typed-choice review, advisory only",
    )
    args = parser.parse_args(argv)
    try:
        if not 2 <= len(args.snapshots) <= 16:
            raise ValueError("AGI requires 2..16 reviewed snapshots")
        packet = review_data_exchange_agi(
            source_snapshots=[
                read_bounded_snapshot(p) for p in args.snapshots
            ],
            tenant_id=args.tenant_id,
            assessed_at=datetime.now(timezone.utc),
            procurement=_procurement(args.procurement),
        )
        packet["local_reasoning_review"] = review_local_reasoning(
            packet, allow_inference=args.local_model,
        )
        packet["laya_shadow_review"] = evaluate_laya_shadow(
            packet, allow_inference=args.laya_shadow,
        )
    except (OSError, TypeError, ValueError, KeyError, OverflowError,
            json.JSONDecodeError, UnicodeError) as exc:
        print(json.dumps({
            "review_status": "HOLD", "error_type": type(exc).__name__,
            "execution_authority": "NONE", "external_actions": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(packet, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
