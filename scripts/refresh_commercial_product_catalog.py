#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.commercial_product_catalog import (
    fetch_catalog,
    write_catalog_snapshot,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 500:
        parser.error("--limit must be between 1 and 500")

    snapshot = fetch_catalog(request_json, limit=args.limit)
    path = write_catalog_snapshot(snapshot)
    print(json.dumps({
        **snapshot,
        "products": [
            {
                "product_code": row.get("product_code"),
                "catalog_state": row.get("catalog_state"),
                "version_state": row.get("version_state"),
                "binding_terms_ready": row.get("binding_terms_ready"),
                "readiness_blockers": row.get("readiness_blockers"),
            }
            for row in snapshot.get("products") or []
        ],
        "snapshot_path": str(path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
