"""Manual, bounded OBSERVE-only assessment of approved source records.

Usage: python -m scripts.preview_construction_data_exchange --input /path/to/records.json
Input: {"records": [...], "rights_review": {...}}. Never use production
contact stores or private conversations as this input.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.data_exchange_construction import build_construction_preview

MAX_INPUT_BYTES = 2 * 1024 * 1024


def load_input(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("input missing or exceeds size cap")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) - {"records", "rights_review"}:
        raise ValueError("input must contain only records and rights_review")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_input(args.input)
        result = build_construction_preview(
            data.get("records"),
            rights_review=data.get("rights_review"),
            observed_at=datetime.now(timezone.utc),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Do not print input contents or secret-bearing paths.
        print(json.dumps({
            "schema_version": "empire.data_exchange.construction_preview.v1",
            "assessment_status": "HOLD",
            "error_type": type(exc).__name__,
            "customer_delivery_enabled": False,
            "execution_authority": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
