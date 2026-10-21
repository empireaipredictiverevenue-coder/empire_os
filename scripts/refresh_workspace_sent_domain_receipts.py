#!/usr/bin/env python3
"""Read-only Workspace SENT-domain history; reuses the existing Gmail timer.

Does not read message bodies, send email, grant outreach rights or write DB.
The metadata snapshot is 0600 and records only domain, Gmail ID and sent date.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
from empire_os.workspace_sent_domain_receipts import (
    WorkspaceSentHistoryError, capture, read_previous,
)
from scripts.reconcile_buyer_email_relationships import atomic_private_write

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime/buyer_network_intelligence/workspace_sent_domain_receipts_latest.json"


def run(*, provider=None, write=False, output: Path = OUTPUT) -> dict:
    result = {
        "status": "HELD",
        "mode": "OBSERVE",
        "source": "existing_authenticated_workspace_mailbox",
        "domains_observed": 0,
        "messages_scanned": 0,
        "snapshot_written": False,
        "database_writes": False,
        "outbound_sent": False,
        "outbound_authorized": False,
        "execution_authority": "NONE",
    }
    provider = provider if provider is not None else GoogleWorkspaceMailboxProvider()
    if not provider.configured:
        result["reason_code"] = "WORKSPACE_GMAIL_READ_SCOPE_UNAVAILABLE"
        return result
    try:
        previous = read_previous(output)
        rows = provider.list_sent(limit=20)
        snapshot = capture(rows, previous)
        result["status"] = "PASS"
        result["domains_observed"] = snapshot["domain_count"]
        result["messages_scanned"] = snapshot["scanned_message_count"]
        if write:
            if output != OUTPUT or output.parent.is_symlink():
                raise WorkspaceSentHistoryError("WORKSPACE_DESTINATION_NOT_CANONICAL")
            atomic_private_write(output, snapshot)
            result["snapshot_written"] = True
        return result
    except Exception as exc:
        # Provider errors, addresses, message IDs and subject/body must not
        # leak into the service logs.
        result["status"] = "HELD"
        result["reason_code"] = (
            str(exc) if isinstance(exc, WorkspaceSentHistoryError)
            else "WORKSPACE_PROVIDER_OR_SOURCE_UNAVAILABLE"
        )
        return result


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--write", action="store_true")
    args = cli.parse_args()
    result = run(write=args.write)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
