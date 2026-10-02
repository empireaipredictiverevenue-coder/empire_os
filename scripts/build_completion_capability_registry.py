#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.completion_capability_registry import build_completion_capability_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--output", default="runtime/execution_plane/empire_completion_capability_registry.json")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    payload = build_completion_capability_registry(root)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(output)
    summary = {
        "schema_version": payload["schema_version"],
        "workstream_count": payload["workstream_count"],
        "checklist": payload["checklist"],
        "states": {},
        "output": str(output.relative_to(root)),
    }
    for row in payload["workstreams"]:
        summary["states"][row["state"]] = summary["states"].get(row["state"], 0) + 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
