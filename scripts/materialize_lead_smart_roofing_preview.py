#!/usr/bin/env python3
"""Generate one PUBLIC, read-only ZIP preview from verified coverage evidence.

Default is check-only. --write explicitly stages the public asset; it never
builds or deploys the website, enables tracking, or authorizes live calls.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from empire_os.lead_smart_homeowner_eligibility import (
    generate_from_files,
)

ROOT = Path("runtime/revenue/lead_smart")
SITE_OUTPUT = Path("apps/empire-public-site/public/roofing-coverage.json")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--out", type=Path, default=SITE_OUTPUT)
    args = p.parse_args()

    manifest = generate_from_files(
        ROOT / "coverage/latest.json",
        ROOT / "coverage/activation/latest.json",
        ROOT / "coverage/intelligence/latest.json",
    )
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8",
                dir=args.out.parent,
                prefix=".roofing-coverage.", suffix=".tmp", delete=False,
            ) as f:
                temp = Path(f.name)
                json.dump(manifest, f, separators=(",", ":"))
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, 0o644)
            os.replace(temp, args.out)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    print(json.dumps({
        "mode": "PREACTIVATION",
        "written": bool(args.write),
        "output": str(args.out) if args.write else None,
        "coverage_zip_count": manifest["count"],
        "preview_expires_at": manifest["expires_at"],
        "call_authorized": False,
        "website_deployed": False,
        "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
