#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.media_claim_verification import (
    refresh_media_claim_verification,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-packs", type=int, default=2)
    parser.add_argument("--max-claims-per-pack", type=int, default=4)
    parser.add_argument("--max-sources-per-pack", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    payload = refresh_media_claim_verification(
        Path(args.repo_root).resolve(),
        max_packs=args.max_packs,
        max_claims_per_pack=args.max_claims_per_pack,
        max_sources_per_pack=args.max_sources_per_pack,
        force=args.force,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
