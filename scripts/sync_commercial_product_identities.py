#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.commercial_product_identity_sync import (
    sync_commercial_product_identities,
)
from empire_os.qualification_worker_v2 import request_json


def main() -> int:
    result = sync_commercial_product_identities(request_json)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
