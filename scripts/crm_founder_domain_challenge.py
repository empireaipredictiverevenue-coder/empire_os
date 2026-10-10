#!/usr/bin/env python3
"""Bounded, manual Cloudflare DNS proof for the existing Empire AI CRM pilot.

PREPARE stores one 24h random challenge locally (not in EmpireDB).
VERIFY checks the exact TXT on both public authoritative nameservers.
Does NOT verify legal ownership or identity, modify DNS, create CRM accounts,
activate memberships, send mail, create login roles or change the CRM API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time

DOMAIN = "empire-ai.co.uk"
FQDN = "_empire-founder-verify.empire-ai.co.uk"
TENANT_ID = "708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT = "founder:phil_livesley"
EXPECTED_NAMESERVERS = ("gracie.ns.cloudflare.com", "nash.ns.cloudflare.com")
STATE_FILE = Path("/srv/empire_os/runtime/crm_pilot/founder_domain_challenge.json")
SCHEMA = "empire.crm.founder_domain_txt_challenge.v1"
VALID_SECONDS = 24 * 3600


def _stamp(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _safe_parent(path: Path) -> None:
    """Never follow a replacement/symlinked local state directory."""
    parent = path.parent
    if parent.exists():
        metadata = parent.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise ValueError("untrusted challenge state directory")
        if metadata.st_mode & 0o077:
            raise ValueError("challenge directory must be private")
    else:
        parent.mkdir(mode=0o700, parents=True)
        parent.chmod(0o700)


def _read(path: Path) -> dict:
    _safe_parent(path)
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o077
        or not 0 < metadata.st_size < 8192):
        raise ValueError("challenge state not a private regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict)
        or value.get("schema") != SCHEMA
        or value.get("domain") != DOMAIN
        or value.get("record_name") != FQDN
        or value.get("tenant_id") != TENANT_ID
        or value.get("subject") != SUBJECT
        or not isinstance(value.get("issued_at"), int)
        or not isinstance(value.get("expires_at"), int)
        or value["expires_at"] - value["issued_at"] != VALID_SECONDS
        or not isinstance(value.get("txt_value"), str)
        or not value["txt_value"].startswith("empire-crm-founder-v1=")
        or len(value["txt_value"].partition("=")[2]) != 48):
        raise ValueError("challenge state identity or shape invalid")
    return value


def prepare(path: Path = STATE_FILE, now: int | None = None) -> dict:
    now = int(time.time() if now is None else now)
    _safe_parent(path)
    try:
        state = _read(path)
    except FileNotFoundError:
        token = secrets.token_hex(24)
        state = {
            "schema": SCHEMA,
            "domain": DOMAIN,
            "record_name": FQDN,
            "record_type": "TXT",
            "tenant_id": TENANT_ID,
            "subject": SUBJECT,
            "txt_value": f"empire-crm-founder-v1={token}",
            "issued_at": now,
            "expires_at": now + VALID_SECONDS,
        }
        encoded = (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode()
        # O_EXCL is deliberate: duplicate/colliding preparations cannot rotate
        # a challenge silently or overwrite another operator's state.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
    if not state["issued_at"] <= now < state["expires_at"]:
        raise ValueError("challenge expired: separate review needed to renew")
    return {
        "schema": SCHEMA,
        "mode": "OBSERVE",
        "status": "AWAITING_FOUNDER_DNS_TXT",
        "record_type": "TXT",
        "record_name": state["record_name"],
        "record_value": state["txt_value"],
        "expires_at_utc": _stamp(state["expires_at"]),
        "dns_changed": False,
        "canonical_db_write": False,
        "crm_membership_activated": False,
        "founder_human_identity_verified": False,
        "legal_company_ownership_verified": False,
        "login_or_credentials_created": False,
        "next_action": "FOUNDER_ADDS_TXT_IN_EXISTING_CLOUDFLARE_DNS",
    }


def _dig_txt(fqdn: str, nameserver: str) -> set[str] | None:
    try:
        p = subprocess.run(
            ["dig", f"@{nameserver}", "+time=2", "+tries=1", "+short", "TXT", fqdn],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    # Our 71-character value never needs RFC1035 TXT segmentation.
    # Refuse unexpected/multi-part quoting rather than loosely normalize.
    return {line.strip().removeprefix('"').removesuffix('"')
            for line in p.stdout.splitlines() if line.strip()
            and line.count('"') in (0, 2)}


def verify(path: Path = STATE_FILE, now: int | None = None) -> dict:
    now = int(time.time() if now is None else now)
    state = _read(path)
    if not state["issued_at"] <= now < state["expires_at"]:
        return {
            "schema": SCHEMA,
            "mode": "OBSERVE",
            "status": "CHALLENGE_EXPIRED_FAIL_CLOSED",
            "dns_control_challenge_verified": False,
            "crm_membership_activated": False,
            "legal_company_ownership_verified": False,
            "login_or_credentials_created": False,
        }
    results = {}
    for ns in EXPECTED_NAMESERVERS:
        txt = _dig_txt(FQDN, ns)
        results[ns] = txt is not None and state["txt_value"] in txt
    valid = all(results.values())
    return {
        "schema": SCHEMA,
        "mode": "OBSERVE",
        "status": "DOMAIN_DNS_TXT_MATCH_REVIEW_ONLY" if valid else "AWAITING_AUTHORITATIVE_DNS_MATCH",
        "authoritative_nameserver_matches": results,
        "dns_control_challenge_verified": valid,
        "verification_tenant_id": TENANT_ID,
        "founder_human_identity_verified": False,
        "legal_company_ownership_verified": False,
        "crm_membership_activated": False,
        "login_or_credentials_created": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "next_action": (
            "REVIEW_INDEPENDENT_FOUNDER_IDENTITY_AND_APPROVE_MEMBERSHIP_ACTIVATION"
            if valid else "FOUNDER_PUBLISHES_DNS_CHALLENGE_OR_WAITS_FOR_PROPAGATION"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = prepare() if args.prepare else verify()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Deliberately suppress file contents, token, addresses and errors.
        result = {
            "schema": SCHEMA,
            "mode": "OBSERVE",
            "status": "CHALLENGE_STATE_UNAVAILABLE_FAIL_CLOSED",
            "dns_control_challenge_verified": False,
            "login_or_credentials_created": False,
            "crm_membership_activated": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
