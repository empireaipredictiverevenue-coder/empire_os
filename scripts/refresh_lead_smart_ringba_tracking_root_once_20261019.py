#!/usr/bin/env python3
"""One-off authenticated Lead Smart tracking freshness refresh; NEVER a call launch.

Reuses existing Ringba observer and existing tracking verifier. Root is needed
ONLY to consume the established 0600 /etc/empire_ringba.env. No new token,
provider mutation, public routing, traffic, payment, call or new daemon.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from scripts.probe_lead_smart_ringba_root_readonly import read_root_config
from empire_os.lead_smart_ringba_api_observer import choose_account, discover_accounts
from empire_os.lead_smart_ringba_tracking_observer import (
    SCHEMA_VERSION as OBS_SCHEMA,
    observe_tracking_objects,
)
from empire_os.lead_smart_tracking_verification import (
    SCHEMA_VERSION as VERIFY_SCHEMA,
    build_tracking_verification,
)

CANON = Path("/srv/empire_os")
OBS = CANON / "runtime/revenue/lead_smart/ringba/tracking_observation/latest.json"
VERIFY = CANON / "runtime/revenue/lead_smart/ringba/tracking_verification/latest.json"
MAX_BYTES = 12000
# Store only the fields emitted by the established sanitized observer.
# Never allow a future malformed provider adapter to smuggle extra raw data
# into the existing world-readable provider evidence projection.
SOURCE_KEYS = frozenset((
    "account_id_persisted", "api_token_persisted", "buyer", "campaign_id",
    "campaign_detail_contains_number", "campaign_detail_proves_id",
    "commercial_activation", "direct_campaign_binding", "endpoint_observations",
    "execution_authority", "inbound_reference_binding",
    "inbound_reference_contains_campaign", "inbound_reference_probed",
    "inbound_reference_status", "mode", "number_lookup_reason", "number_object",
    "number_object_found", "observed_at", "provider", "provider_binding_verified",
    "raw_provider_payload_persisted", "revenue_recognized", "routing_enabled",
    "routing_verified_change", "schema_version", "tracking_number",
    "tracking_verification_candidate", "tracking_verified_change", "traffic_enabled",
    "vertical",
))


def payload(data: dict) -> bytes:
    encoded = (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    if len(encoded) > MAX_BYTES:
        raise ValueError("evidence_too_large")
    return encoded


def checked_payloads(source: dict, *, now: datetime | None = None) -> tuple[bytes, bytes]:
    if (not isinstance(source, dict) or source.get("schema_version") != OBS_SCHEMA
            or set(source) != SOURCE_KEYS):
        raise ValueError("tracking_schema_untrusted")
    if not (
        source.get("mode") == "OBSERVE"
        and source.get("provider_binding_verified") is True
        and source.get("tracking_verification_candidate") is True
        and source.get("api_token_persisted") is False
        and source.get("account_id_persisted") is False
        and source.get("raw_provider_payload_persisted") is False
        and source.get("traffic_enabled") is False
        and source.get("routing_enabled") is False
        and source.get("commercial_activation") is False
        and source.get("revenue_recognized") is False
        and source.get("execution_authority") == "NONE"
    ):
        raise ValueError("tracking_source_untrusted")
    original = payload(source)
    digest = hashlib.sha256(original).hexdigest()
    verified = build_tracking_verification(source, source_sha256=digest, now=now)
    if not (
        verified.get("schema_version") == VERIFY_SCHEMA
        and verified.get("state") == "VERIFIED"
        and verified.get("tracking_verified") is True
        and verified.get("routing_verified") is False
        and verified.get("routing_enabled") is False
        and verified.get("traffic_enabled") is False
        and verified.get("execution_authority") == "NONE"
        and verified.get("source_sha256") == digest
    ):
        raise ValueError("tracking_verification_untrusted")
    return original, payload(verified)


def inspect_target(path: Path) -> None:
    parent = path.parent
    d = parent.lstat()
    if not stat.S_ISDIR(d.st_mode) or stat.S_ISLNK(d.st_mode) or d.st_mode & 0o002:
        raise ValueError("untrusted_existing_evidence_parent")
    p = path.lstat()
    if (not stat.S_ISREG(p.st_mode) or stat.S_ISLNK(p.st_mode)
            or p.st_size > MAX_BYTES or p.st_nlink != 1
            or p.st_mode & 0o002):
        raise ValueError("untrusted_existing_evidence_file")


def replace_bytes(path: Path, data: bytes) -> None:
    inspect_target(path)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tracking-evidence-", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            os.fchmod(f.fileno(), 0o644)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def refresh(
    *,
    apply: bool,
    observer=observe_tracking_objects,
    credential_reader=read_root_config,
    accounts_reader=discover_accounts,
    account_chooser=choose_account,
    current_root: Path = CANON,
    observed_at: datetime | None = None,
    observation_path: Path = OBS,
    verification_path: Path = VERIFY,
) -> dict:
    report = {
        "schema_version": "empire.lead_smart.root_tracking_refresh_once.v1",
        "mode": "OBSERVE" if not apply else "TRACKING_EVIDENCE_ONLY",
        "status": "HELD",
        "tracked_campaign_binding_verified": False,
        "tracking_verification_refreshed": False,
        "buyer_route_independently_verified": False,
        "buyer_leg_connected": False,
        "recording_governance_verified": False,
        "call_admission_authorized": False,
        "traffic_enabled": False,
        "external_provider_mutation": False,
        "service_restart": False,
        "buyer_email_sent": False,
        "payment_executed": False,
        "credentials_persisted": False,
    }
    try:
        if (os.geteuid() != 0 or Path.cwd().resolve() != current_root
                or current_root.is_symlink()):
            report["status"] = "HOLD_ROOT_OR_CANONICAL_CWD_REQUIRED"
            return report
        inspect_target(observation_path)
        inspect_target(verification_path)
        credentials = credential_reader()
        secret = credentials["RINGBA_API_TOKEN"]
        account = account_chooser(
            accounts_reader(secret), credentials.get("RINGBA_ACCOUNT_ID")
        )
        observed = observer(token=secret, account_id=account)
        source, verified = checked_payloads(observed, now=observed_at)
        report["tracked_campaign_binding_verified"] = True
        if not apply:
            report["status"] = "FRESH_TRACKING_OBSERVABLE_NO_WRITES"
            return report
        replace_bytes(observation_path, source)
        replace_bytes(verification_path, verified)
        reread = json.loads(verification_path.read_bytes())
        if (not reread.get("tracking_verified") is True
                or reread.get("source_sha256") != hashlib.sha256(
                    observation_path.read_bytes()).hexdigest()):
            report["status"] = "HOLD_WRITTEN_DIGEST_UNVERIFIED"
            return report
        report["tracking_verification_refreshed"] = True
        report["status"] = "TRACKING_FRESH_NO_CALL_AUTHORITY"
        return report
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        # Provider exceptions or OS errors could include raw account/phone
        # content. Never output exception messages or source credentials.
        report["status"] = "HOLD_PROVIDER_OR_SOURCE_UNVERIFIED"
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read-only", action="store_true")
    mode.add_argument("--apply-founder-approved-tracking-observation-only", action="store_true")
    args = parser.parse_args()
    result = refresh(apply=args.apply_founder_approved_tracking_observation_only)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in (
        "FRESH_TRACKING_OBSERVABLE_NO_WRITES",
        "TRACKING_FRESH_NO_CALL_AUTHORITY",
    ) else 2

if __name__ == "__main__":
    raise SystemExit(main())
