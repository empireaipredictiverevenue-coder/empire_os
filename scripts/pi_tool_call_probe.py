#!/usr/bin/env python3
from __future__ import annotations

import json
from empire_os.pi_tool_call_probe import probe_local_tool_calls

def main() -> int:
    result = probe_local_tool_calls()
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
