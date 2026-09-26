#!/usr/bin/env python3
"""Run the governed Empire Coder Aider mutation capability probe."""
from __future__ import annotations

import json

from empire_os.aider_capability_probe import probe_aider_mutation


def main() -> int:
    result = probe_aider_mutation()
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
