#!/usr/bin/env python3
"""Read-only seven-thread founder acquisition review, no new OAuth, no sends.

The existing Google Workspace provider verifies primary account and scopes.
Never place this into a generic unauthenticated API or send public alerts with
person data.  --write updates one private snapshot, not the prospect CSV/CRM.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile

from empire_os.founder_acquisition_autopilot import EvidenceHeld, collect, load_ledger, SOURCE
from empire_os.founder_acquisition_source_refresh import refresh_pending
from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider

DEFAULT_ROOT = Path("/srv/empire_os")
OUT = Path("runtime/founder_acquisition/founder_reply_review_latest.json")
PUBLIC_OUT = Path("runtime/founder_acquisition/public_source_review_latest.json")


def _read_private_snapshot(output: Path):
    if output.is_symlink():
        raise EvidenceHeld("UNSAFE_EXISTING_SNAPSHOT")
    if not output.exists():
        return None
    if (not output.is_file() or output.stat().st_size > 180_000
            or stat.S_IMODE(output.stat().st_mode) != 0o600):
        raise EvidenceHeld("UNSAFE_EXISTING_SNAPSHOT")
    return json.loads(output.read_text(encoding="utf-8"))


def _write_private_snapshot(output: Path, obj: dict) -> None:
    if output.is_symlink() or output.parent.is_symlink():
        raise EvidenceHeld("UNSAFE_SNAPSHOT_DESTINATION")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".review-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(obj, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def refresh_unsent_sources(root: Path, *, ledger: dict, now, fetch=None) -> dict:
    """Optional daily first-party evidence; never obstruct real reply monitoring."""
    from empire_os.founder_acquisition_source_refresh import fetch_profile
    try:
        output = root / PUBLIC_OUT
        previous = _read_private_snapshot(output)
        pending_names = {r["company"] for r in ledger["pending"]}
        with (root / SOURCE).open(newline="", encoding="utf-8") as handle:
            original = list(csv.DictReader(handle))
        pending = [r for r in original if r["company"] in pending_names]
        if len(pending) != len(pending_names):
            raise EvidenceHeld("INCOMPLETE_PROSPECT_SOURCE_INPUT")
        results = refresh_pending(
            pending, previous=previous, now=now or datetime.now(timezone.utc),
            fetch=fetch or fetch_profile,
            max_fetch=2,
        )
        _write_private_snapshot(output, results)
        return {
            "source_refresh_status": results["status"],
            "source_profiles_reviewed": results["reviewed_profiles"],
            "source_profiles_verified": results["verified_public_profiles"],
            "unsent_draft_reviews": len(results["unsent_review_drafts"]),
        }
    except Exception:
        return {"source_refresh_status": "HELD_SOURCE_REFRESH",
                "source_profiles_reviewed": None,
                "source_profiles_verified": None,
                "unsent_draft_reviews": None}


def run(root: Path, *, provider=None, write: bool = False, now=None, source_fetch=None) -> dict:
    status = {
        "schema_version": "empire.founder_acquisition_cycle_status.v1",
        "status": "HELD_NOT_AUTHENTICATED", "outbound_sent": False,
        "database_writes": False, "no_new_services": True,
        "snapshot_written": False, "automatic_send_eligible": False,
    }
    try:
        root = Path(root).resolve(strict=True)
        ledger = load_ledger(root)
        provider = provider if provider is not None else GoogleWorkspaceMailboxProvider()
        if not provider.configured:
            raise EvidenceHeld("EXISTING_WORKSPACE_MAILBOX_NOT_CONFIGURED")
        output = root / OUT
        previous = _read_private_snapshot(output) if write else None
        reviewed = collect(provider._service(), ledger, now=now or datetime.now(timezone.utc), previous=previous)
        if reviewed["sent_anchors_verified"] != 7 or reviewed["outbound_sent"] is not False:
            raise EvidenceHeld("INCOMPLETE_VERIFICATION")
        if write:
            _write_private_snapshot(output, reviewed)
            status.update(refresh_unsent_sources(root, ledger=ledger, now=now, fetch=source_fetch))
        status.update({
            "status": reviewed["status"],
            "monitored_threads": 7,
            "inbound_header_candidate_count": reviewed["inbound_header_candidate_count"],
            "new_inbound_header_candidates": reviewed["new_inbound_header_candidates"],
            "next_unsent_candidate_count": len(ledger["pending"]),
            "snapshot_written": write,
        })
    except Exception as exc:
        status["reason_code"] = str(exc) if isinstance(exc, EvidenceHeld) else "PROVIDER_OR_SOURCE_UNVERIFIED"
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = run(Path(args.repo_root), write=args.write)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SOURCE_ANCHORS_VERIFIED_REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
