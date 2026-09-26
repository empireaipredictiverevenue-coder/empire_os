#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.intelligence_nodes import NODES


def main() -> int:
    payload = {
        "schema_version": "empire.intelligence_nodes.v1",
        "count": len(NODES),
        "nodes": [node.as_dict() for node in NODES],
        "positioning": "intelligence_and_revenue_operating_system",
        "scrapers_are_sensors": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
