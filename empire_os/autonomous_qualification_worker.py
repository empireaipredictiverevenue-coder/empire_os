#!/usr/bin/env python3
"""Compatibility CLI for canonical qualification v2.

The historical autonomous qualifier no longer owns transport, credentials, or a
parallel scoring implementation. It resolves one canonical prospect through the
vendor-neutral qualification repository and delegates to qualification v2.
"""
from __future__ import annotations

import argparse
import json

from empire_os.qualification_worker_v2 import fetch_prospect, qualify_prospect


def qualify(prospect_id: str) -> dict:
    prospect = fetch_prospect(str(prospect_id))
    result = qualify_prospect(prospect)
    return {
        "ok": True,
        **result,
        "scoring_version": "v2",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prospect-id", required=True)
    args = parser.parse_args()
    print(json.dumps(qualify(args.prospect_id), indent=2, default=str))


if __name__ == "__main__":
    main()
