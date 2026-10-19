"""Historical Listmonk recovery and safe audience eligibility preflight.

Existing Listmonk DB/audience belongs to its original owner and cannot be
reconstituted from historical Git commit messages. This code DOES NOT reuse
historic credentials (which require rotation), open a sending port, create
subscribers, import any lead file, connect to SMTP/Brevo or run campaigns.
An old B2B contact or EmpireDB prospect != a marketing opt-in.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any

SCHEMA = "empire.listmonk_private_recovery.v1"
CONSENT_SCHEMA = "empire.listmonk_marketing_consent_preflight.v1"
MAX_ROWS = 1500
LEGACY_COMMIT_REFS = {
    "listmonk_import_leads": "f6038ca1:empire_os/listmonk_import_leads.py",
    "listmonk_bulk_campaign": "8dc9c512:empire_os/listmonk_bulk_campaign.py",
    "smtp_brevo_relay": "8dc9c512:empire_os/smtp_brevo_relay.py",
}


def review_listmonk_audience_eligibility(rows: Sequence[Mapping[str, Any]], *,
                                          now: datetime | None = None) -> dict[str, Any]:
    """Aggregate opt-in readiness, never export subscriber identifiers.

    A verified double-opt-in receipt, an explicit marketing purpose and a
    clean suppression state are required. Historical import lists without
    those are quarantined. Contact history is NOT marketing consent.
    """
    if not isinstance(rows, (list, tuple)) or len(rows) > MAX_ROWS:
        raise ValueError("listmonk_audience_count_unbounded")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("aware_time_required")
    counts = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("untrusted_audience_row")
        if any(type(row.get(flag)) is not bool for flag in (
            "suppressed", "unsubscribed", "bounced",
        )):
            counts["suppression_state_unverified"] += 1
            continue
        if row["suppressed"] or row["unsubscribed"] or row["bounced"]:
            counts["explicit_suppression_hold"] += 1
            continue
        if any(type(row.get(flag)) is not bool for flag in (
            "double_opt_in_confirmed", "marketing_purpose_consented",
            "canonical_suppression_checked", "recipient_address_verified",
        )):
            counts["missing_verifiable_consent_or_suppression"] += 1
            continue
        if not all(row.get(flag) is True for flag in (
            "double_opt_in_confirmed", "marketing_purpose_consented",
            "canonical_suppression_checked", "recipient_address_verified",
        )):
            counts["missing_verifiable_consent_or_suppression"] += 1
            continue
        if row.get("consent_purpose") != "empire_ai_marketing_newsletter":
            counts["wrong_marketing_purpose"] += 1
            continue
        if row.get("source_provenance_verified") is not True:
            counts["missing_verifiable_provenance"] += 1
            continue
        try:
            stamp = datetime.fromisoformat(str(row["consented_at"]).replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp > current:
                raise ValueError("invalid_consent_timestamp")
        except (ValueError, KeyError, TypeError):
            counts["missing_or_future_consent_timestamp"] += 1
            continue
        # Even eligible rows require an independent Listmonk restore,
        # identity binding and human send approval.
        counts["review_eligible_not_imported"] += 1
    return {
        "schema_version": CONSENT_SCHEMA,
        "state": "AUDIENCE_REVIEW_ONLY",
        "historical_records_checked": len(rows),
        "review_eligible_not_imported": counts["review_eligible_not_imported"],
        "held_count": len(rows) - counts["review_eligible_not_imported"],
        "hold_reasons": {k: v for k, v in sorted(counts.items())
                         if k != "review_eligible_not_imported"},
        "canonical_empiredb_writes": False,
        "listmonk_subscriber_writes": False,
        "campaign_send_authorized": False,
        "mailing_list_import_authorized": False,
        "execution_authority": "none",
    }


def inspect_legacy_listmonk(root: Path, *,
                            localhost_port: int = 9000,
                            port_probe=None,
                            git_probe=None) -> dict[str, Any]:
    """Only local health and legacy *code* checks, no secrets or Docker access."""
    if localhost_port != 9000:
        raise ValueError("unapproved_listmonk_local_port")
    if not root.is_dir():
        raise ValueError("invalid_canonical_repo")
    if port_probe is None:
        def port_probe(port: int) -> bool:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return True
            except (TimeoutError, ConnectionError, OSError):
                return False
    if git_probe is None:
        def git_probe(ref: str) -> bool:
            try:
                done = subprocess.run(
                    ["git", "-C", str(root), "cat-file", "-e", ref],
                    check=False, timeout=5, capture_output=True,
                )
                return done.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                return False
    legacy = {name: bool(git_probe(ref)) for name, ref in LEGACY_COMMIT_REFS.items()}
    listening = bool(port_probe(localhost_port))
    binary = shutil.which("listmonk") is not None
    code_present = any(legacy.values())
    return {
        "schema_version": SCHEMA,
        "mode": "LOCAL_READ_ONLY_RESTORE_PREFLIGHT",
        "state": ("RUNNING_PORT_REQUIRES_AUTHENTICATED_INSTANCE_AUDIT"
                  if listening else
                  "LEGACY_CODE_RECOVERABLE_DATA_NOT_VERIFIED"
                  if code_present else "NO_LEGACY_CODE_OR_RUNNING_SERVICE"),
        "historical_git_components_found": legacy,
        "legacy_application_code_recoverable": code_present,
        "listmonk_binary_on_path": binary,
        "localhost_9000_listening": listening,
        "original_audience_rows_recovered": None,
        "historical_audience_claim_unverified": "628-629 records reported by historic commit messages, not current database evidence",
        "historic_secret_reuse_prohibited": True,
        "smtp_delivery_enabled": False,
        "legacy_bulk_send_disabled": True,
        "database_recovery_verified": False,
        "credential_rotation_required": True,
        "consent_and_canonical_suppression_recheck_required": True,
        "recovery_blockers": [
            "Docker/volume metadata requires authorised root-owned inventory",
            "Original Listmonk PostgreSQL database/volume backup not confirmed",
            "Historical authentication and relay secrets must be rotated",
            "Audience consent/suppression evidence must be independently reconciled",
            "Dedicated private loopback service and sender-disabled smoke tests required",
        ],
        "automatic_list_import_authorized": False,
        "automatic_outbound_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }
