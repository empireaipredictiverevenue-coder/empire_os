#!/usr/bin/env python3
"""Use EXISTING authenticated Workspace Gmail provider for six sent threads.

No new OAuth, Gmail send, CRM write or systemd timer. Produces PRIVATE bounded
metadata only; stdout contains counts or a fail-closed reason code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
from empire_os.workspace_heat_pump_reply_tracking import (
    ANCHORS as HEAT_ANCHORS, collect_heat_pump_threads,
    newly_observed_heat_pump_candidates,
)
from empire_os.workspace_solar_reply_tracking import (
    EvidenceHeld, collect_workspace_solar_threads,
    newly_observed_workspace_replies,
)
from scripts.reconcile_buyer_email_relationships import atomic_private_write

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime/buyer_network_intelligence/workspace_solar_outreach_reply_review_latest.json"
HEAT_OUTPUT = ROOT / "runtime/buyer_network_intelligence/workspace_heat_pump_reply_review_latest.json"


def run(*, provider=None, write: bool = False, now=None, output: Path = OUTPUT) -> dict:
    flags = {
        "schema_version": "empire.workspace_solar_outreach_poll.v1",
        "status": "HELD_WORKSPACE_READER_UNAVAILABLE",
        "mode": "OBSERVE",
        "account_scope": "EMPIRE_WORKSPACE_NOT_PERSONAL_GMAIL",
        "monitored_threads": 6,
        "verified_sent_anchors_in_live_mailbox": 0,
        "inbound_header_candidates": None,
        "new_inbound_header_candidates": None,
        "source_scan_complete": False,
        "snapshot_written": False,
        "heat_pump_status": "HELD_HEAT_PUMP_THREADS_NOT_SCANNED",
        "heat_pump_monitored_threads": len(HEAT_ANCHORS),
        "heat_pump_verified_sent_anchors": 0,
        "heat_pump_inbound_header_candidates": None,
        "heat_pump_new_inbound_candidates": None,
        "heat_pump_snapshot_written": False,
        "database_writes": False,
        "outbound_sent": False,
        "automatic_reply_authorized": False,
        "execution_authority": "none",
    }
    provider = provider if provider is not None else GoogleWorkspaceMailboxProvider()
    if not provider.configured:
        flags["reason_code"] = "WORKSPACE_GMAIL_READ_SCOPE_NOT_CONFIGURED"
        return flags
    try:
        # _service is the EXISTING authenticated and sender-identity checked
        # provider transport. NEVER instantiate an unverified second OAuth
        # client or use the personal-buyer Gmail token for these threads.
        service = provider._service()
        reviewed = collect_workspace_solar_threads(
            service, now=now or datetime.now(timezone.utc)
        )
        if reviewed["verified_sent_anchors"] != 6 or reviewed["monitored_threads"] != 6:
            raise EvidenceHeld("INCOMPLETE_ANCHOR_VERIFICATION")
        if write:
            # Existing historical evidence is private; never overwrite unknown
            # or weakened file permissions with a supposedly healthy run.
            if output != OUTPUT or output.is_symlink():
                raise EvidenceHeld("UNTRUSTED_OUTPUT_DESTINATION")
            previous = None
            if output.exists():
                if (not output.is_file() or output.stat().st_size > 180_000
                        or stat.S_IMODE(output.stat().st_mode) != 0o600):
                    raise EvidenceHeld("UNSAFE_PREVIOUS_WORKSPACE_SNAPSHOT")
                try:
                    previous = json.loads(output.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    raise EvidenceHeld("INVALID_PREVIOUS_WORKSPACE_JSON") from None
            flags["new_inbound_header_candidates"] = newly_observed_workspace_replies(
                reviewed, previous
            )
            reviewed["new_inbound_header_candidate_count"] = flags["new_inbound_header_candidates"]
            atomic_private_write(output, reviewed)
            flags["snapshot_written"] = True
        # Additional pre-existing heat-pump threads use this SAME Workspace
        # read-only client and EXISTING 15-minute cycle. Failure is isolated
        # from the six historical Workspace solar threads.
        try:
            heat = collect_heat_pump_threads(
                service, now=now or datetime.now(timezone.utc)
            )
            if heat["verified_original_sends"] != len(HEAT_ANCHORS):
                raise EvidenceHeld("HEAT_PUMP_SENT_COVERAGE_INCOMPLETE")
            if write:
                if (HEAT_OUTPUT.is_symlink() or
                        not HEAT_OUTPUT.parent.is_dir() or
                        HEAT_OUTPUT.parent.is_symlink()):
                    raise EvidenceHeld("HEAT_PUMP_PRIVATE_DESTINATION_UNSAFE")
                previous_heat = None
                if HEAT_OUTPUT.exists():
                    if (not HEAT_OUTPUT.is_file()
                            or HEAT_OUTPUT.stat().st_size > 50000
                            or stat.S_IMODE(HEAT_OUTPUT.stat().st_mode) != 0o600):
                        raise EvidenceHeld("HEAT_PUMP_PREVIOUS_SNAPSHOT_UNSAFE")
                    previous_heat = json.loads(
                        HEAT_OUTPUT.read_text(encoding="utf-8")
                    )
                delta = newly_observed_heat_pump_candidates(
                    heat, previous_heat
                )
                heat["new_inbound_header_candidate_count"] = delta
                atomic_private_write(HEAT_OUTPUT, heat)
                flags["heat_pump_new_inbound_candidates"] = delta
                flags["heat_pump_snapshot_written"] = True
            flags["heat_pump_status"] = heat["status"]
            flags["heat_pump_verified_sent_anchors"] = len(HEAT_ANCHORS)
            flags["heat_pump_inbound_header_candidates"] = (
                heat["inbound_header_candidate_count"]
            )
        except Exception:
            # This auxiliary cohort must not leak source/provider diagnostics
            # or erase the older original cohort's accepted evidence snapshot.
            flags["heat_pump_status"] = "HELD_HEAT_PUMP_REPLY_REVIEW_UNAVAILABLE"
        flags.update({
            "status": "WORKSPACE_SENT_ANCHORS_VERIFIED_REVIEW_ONLY",
            "verified_sent_anchors_in_live_mailbox": 6,
            "inbound_header_candidates": reviewed["inbound_header_candidate_count"],
            "source_scan_complete": True,
            "reason_code": "NONE",
        })
    except Exception as exc:
        # Never expose provider errors, tokens, email bodies or customer data.
        flags["status"] = "HELD_WORKSPACE_READER_UNAVAILABLE"
        flags["snapshot_written"] = False
        flags["reason_code"] = (
            str(exc) if isinstance(exc, EvidenceHeld)
            else "WORKSPACE_PROVIDER_READ_UNVERIFIED"
        )
    return flags


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="Persist a private metadata-only evidence snapshot if eligible")
    opts = parser.parse_args()
    result = run(write=opts.write)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["source_scan_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
