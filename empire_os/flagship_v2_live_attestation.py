"""Exact published V2 STATIC SOURCE attestation for founder control.

The historical checkout pin remains historical; this observes a separately
founder-approved exact full-site release. It does not approve checkout money,
editorial pages, outbound, buyer consent, or new publication authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

CANONICAL_ROOT = Path("/srv/empire_os")
V2_RECEIPT = Path(
    "/home/ubuntu/empire_releases/flagship_checkout_union_20261020"
    "/RELEASE_CANDIDATE_RECEIPT.json"
)
EXPECTED_INVENTORY = "650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3"
EXPECTED_SCHEMA = "empire.website.flagship_checkout_full_export_union.v1"
PUBLIC_RELATIVE = Path("apps/empire-public-site/out")


def _verified_site_source(*, site: Path, receipt: Path) -> bool:
    if (
        receipt.is_symlink() or not receipt.is_file()
        or receipt.stat().st_size > 250_000
    ):
        return False
    owner = json.loads(receipt.read_text(encoding="utf-8"))
    if (
        not isinstance(owner, dict)
        or owner.get("schema_version") != EXPECTED_SCHEMA
        or owner.get("status") != "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED"
        or owner.get("candidate_integrity_verified") is not True
        or owner.get("new_public_release_authorized") is not False
        or owner.get("public_files_modified") is not False
        or owner.get("mixed_next_build_routing_navigation_review_required") is not True
    ):
        return False
    expected = owner.get("static_file_sha256")
    if not isinstance(expected, dict) or len(expected) != 632:
        return False
    if (
        sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        != EXPECTED_INVENTORY
    ):
        return False
    if not site.is_dir() or site.is_symlink():
        return False
    observed = set()
    total_bytes = 0
    for path in site.rglob("*"):
        if path.is_symlink():
            return False
        if path.is_dir():
            continue
        if not path.is_file():
            return False
        relative = path.relative_to(site).as_posix()
        if relative not in expected or relative in observed:
            return False
        if type(expected[relative]) is not str or len(expected[relative]) != 64:
            return False
        observed.add(relative)
        with path.open("rb") as f:
            digest = sha256()
            while block := f.read(65_536):
                digest.update(block)
                total_bytes += len(block)
                if total_bytes > 300_000_000:
                    return False
        if digest.hexdigest() != expected[relative]:
            return False
    return observed == set(expected)


def attest_public_flagship_v2(root: Path) -> dict[str, Any]:
    if root.resolve() != CANONICAL_ROOT:
        return {
            "status": "LIVE_V2_PUBLICATION_NOT_CHECKED_NONCANONICAL_ROOT",
            "exact_published_bytes_verified": None,
        }
    try:
        verified = _verified_site_source(
            site=root / PUBLIC_RELATIVE,
            receipt=V2_RECEIPT,
        )
    except (OSError, TypeError, ValueError, OverflowError):
        verified = False
    return {
        "status": (
            "EXACT_APPROVED_V2_PUBLIC_STATIC_BYTES_VERIFIED" if verified
            else "V2_PUBLICATION_SOURCE_NOT_VERIFIED"
        ),
        "exact_published_bytes_verified": verified,
        "approved_inventory_sha256": EXPECTED_INVENTORY if verified else None,
        "verified_static_file_count": 632 if verified else None,
        "historical_october_checkout_manifest_replaced": False,
        "payment_and_outbound_authorized": False,
        "legal_or_unapproved_editorial_activated": False,
    }
