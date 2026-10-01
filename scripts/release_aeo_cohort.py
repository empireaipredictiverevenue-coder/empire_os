#!/usr/bin/env python3
"""Build or atomically apply a bounded, zero-paid AEO release manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.aeo_release import (
    DEFAULT_AEO_ROOT, DEFAULT_RECOVERY, DEFAULT_RELEASE,
    build_release_manifest,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--page", action="append", required=True, help="niche:metro")
    p.add_argument("--evidence-ref", action="append", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    pages = []
    for raw in args.page:
        if ":" not in raw:
            raise SystemExit("--page must be niche:metro")
        pages.append(tuple(raw.split(":", 1)))
    manifest = build_release_manifest(
        pages,
        aeo_root=DEFAULT_AEO_ROOT,
        recovery_path=DEFAULT_RECOVERY,
        evidence_refs=args.evidence_ref,
    )
    target = DEFAULT_RELEASE if args.apply else args.output
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        tmp.replace(target)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
