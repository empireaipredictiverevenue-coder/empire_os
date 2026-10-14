"""Read-only, stage-only Postfix Maildir custody check with SHA256 readback.

One explicit synthetic identity; no network, MTA execution or data mutation.
No script arguments can waive fixed root/mailbox owner requirements.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.owned_postfix_maildir_custody import inspect_fixture_maildir_custody
from scripts.probe_postfix_synthetic_delivery import (
    MESSAGE_ID, RCPT, MARKER,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one protected offline Postfix Maildir item; no writes"
    )
    parser.add_argument("--approved-isolated-custody-check", action="store_true")
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--previous-sha256")
    params = parser.parse_args(argv)
    if (not params.approved_isolated_custody_check
            or params.staging_root is None):
        print(json.dumps({
            "status": "ISOLATED_MAILDIR_CUSTODY_CHECK_NOT_REQUESTED",
            "network_connections": 0,
            "database_reads": False,
            "mailbox_mutations": False,
            "production_mx_changed": False,
        },sort_keys=True))
        return 0
    try:
        outcome = inspect_fixture_maildir_custody(
            params.staging_root,
            expected_rfc_message_id=MESSAGE_ID,
            expected_recipient=RCPT,
            expected_body_marker=MARKER,
            previous_sha256=params.previous_sha256,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({
            "status": "HOLD_ISOLATED_MAILDIR_CUSTODY_UNVERIFIED",
            "error_type": type(exc).__name__,
            "network_connections": 0,
            "mailbox_mutations": False,
            "production_mx_changed": False,
        },sort_keys=True))
        return 2
    print(json.dumps(outcome,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
