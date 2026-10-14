#!/usr/bin/env python3
"""Live, non-sending proof for explicitly selected founder Workspace inbox.

Reads at most one provider-only message per folder, prints no message content.
Does not convert replies into verified commercial conversations or sends.
"""
from __future__ import annotations

import json

from scripts.verify_owned_imap_mailbox import service_readiness_report


def main() -> int:
    result = service_readiness_report(
        probe=True,
        expected_provider="google_workspace",
        startup_attempts=1,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READ_PROBE_SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
