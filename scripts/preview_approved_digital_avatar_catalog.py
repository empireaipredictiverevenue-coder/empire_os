#!/usr/bin/env python3
"""Render the three founder-approved Avatar *pending proposal* RPC previews.

No invocation/apply option exists. The canonical EmpireDB catalog stays intact.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from empire_os.digital_avatar_approved_catalog_preview import (
    CatalogStagingHold,
    build_approved_avatar_catalog_preview,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--output", default="",
                        help="Optional output JSON path; never writes a product catalog")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    source = root / "runtime/commercial_catalog/latest.json"
    try:
        if source.is_symlink() or source.stat().st_size > 2_000_000:
            raise CatalogStagingHold("canonical_catalog_source_unsafe_or_unbounded")
        packet = json.loads(source.read_text(encoding="utf-8"))
        result = build_approved_avatar_catalog_preview(packet)
        if args.output:
            dest = Path(args.output).resolve()
            expected = root / "runtime/commercial_proposals/digital_avatar_approved_price_v1.json"
            if dest != expected or dest.is_symlink():
                raise CatalogStagingHold("output_must_be_exact_first_party_preview_path")
            if dest.exists():
                old = json.loads(dest.read_text())
                # A replay cannot replace or silently change captured policy.
                if old != result:
                    raise CatalogStagingHold("existing_proposal_requires_separate_revision")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                body = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
                fd, name = tempfile.mkstemp(
                    dir=dest.parent, prefix=".avatar_policy_", suffix=".pending",
                )
                try:
                    with os.fdopen(fd,"wb") as handle:
                        handle.write(body)
                        handle.flush()
                        os.fsync(handle.fileno())
                    # Exclusive hard link: never overwrite another agent's work.
                    os.link(name,dest)
                finally:
                    Path(name).unlink(missing_ok=True)
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({
            "status": "HELD", "reason": f"{type(exc).__name__}:{str(exc)[:130]}",
            "database_mutation": False, "execution_authority": "none",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
