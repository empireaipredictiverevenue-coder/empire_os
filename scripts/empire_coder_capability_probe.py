#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.empire_coder_capability_probe import (
    probe_empire_coder_structured_patch,
)


def main() -> int:
    result = probe_empire_coder_structured_patch()
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
