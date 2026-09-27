#!/usr/bin/env python3
from __future__ import annotations

import json
from empire_os.builder_capabilities import record_builder_capability
from empire_os.pi_tool_call_probe import probe_local_tool_calls

def main() -> int:
    result = probe_local_tool_calls()
    payload = result.as_dict()
    record_builder_capability(
        "pi",
        "code_mutation",
        ready=result.ok,
        reason=result.reason,
        model=result.model,
        evidence={
            "tool_call_count": result.tool_call_count,
            "tool_name": result.tool_name,
            "arguments_valid_json": result.arguments_valid_json,
            "raw_content_present": result.raw_content_present,
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
