"""Independent, read-only proof: reviewed Lead Smart content survived founder's V2 site release.

This module does not authorize live calls, recordings, traffic, payout, routing,
buyer terms, or any extended campaign. Exact receipt, page and source digests
are immutable acceptance inputs; changing them requires separate review.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import stat
from typing import Any

ROOT = Path("/srv/empire_os")
SITE = ROOT / "apps/empire-public-site/out"
REVIEWED_ROOFING = Path(
    "/home/ubuntu/empire_releases/flagship_checkout_union_20261020/out.pre-v2-public/roofing.html"
)
V2_RECEIPT = Path("/var/backups/empire-website/FLAGSHIP_V2_PUBLICATION_RECEIPT_20261020.json")
V2_MANIFEST = Path(
    "/home/ubuntu/empire_releases/flagship_checkout_union_20261020/RELEASE_CANDIDATE_RECEIPT.json"
)
RUNTIME_ATTESTATION = Path("/etc/empire_lead_smart_v2_landing_compatibility.json")

FROZEN_SOURCE_SHA = "62e922bd99b32fec96e0053656050527013120ccb593f669fdaa4c5010ccefcf"
FROZEN_APPROVED_SOURCE_SHA = "faea59c0d8c6d510db8af876a53af439eac41e294f8d348e20576c75bd43cccb"
REVIEWED_HTML_SHA = "8e5d0b360832cf3753a85d4683a93b7f361d6b7212f5545063f65447af04966b"
V2_HTML_SHA = "913832d837bd45bb4f475eb4f83a8f7715e0653d55fcb1f8903f2b2114c867cf"
V2_RECEIPT_SHA = "7b81defbdeecda420b1a97ccc9bc6c57cce1fb0fc2fdafe46cbe882c2ee5e406"
V2_MANIFEST_SHA = "475daf56c67d0a1dd29f36d7d1ad93d94d7e89c4355bb7bb13abcc0a4361507d"
V2_INVENTORY_SHA = "650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3"
SCHEMA = "empire.lead_smart.v2_landing_semantic_compatibility.v1"


def sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512_000:
        raise ValueError("missing_or_untrusted_file")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConsumerDOM(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.excluded = 0
        self.words: list[str] = []
        self.anchors: list[tuple] = []
        self.forms: list[tuple] = []
        self.images: list[tuple] = []
        self.select_meta: list[tuple] = []

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        data = dict(attrs)
        if tag in ("script", "style"):
            self.excluded += 1
        elif tag == "a":
            self.anchors.append((data.get("href"), data.get("target"), data.get("rel")))
        elif tag in ("form", "input", "button", "select", "textarea"):
            self.forms.append((tag, tuple(sorted(
                (k, v) for k, v in data.items()
                if k not in ("class", "style", "id", "aria-label")
            ))))
        elif tag == "img":
            self.images.append((data.get("src"), data.get("alt")))
        elif tag == "meta" and data.get("name") in ("description", "robots"):
            self.select_meta.append((data.get("name"), data.get("content")))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.excluded:
            self.excluded -= 1

    def handle_data(self, value: str) -> None:
        if not self.excluded and value.strip():
            self.words.append(value.strip())

    @classmethod
    def of(cls, raw: bytes) -> "ConsumerDOM":
        parsed = cls()
        parsed.feed(raw.decode("utf-8"))
        return parsed

    def equivalent(self, other: "ConsumerDOM") -> bool:
        return all(getattr(self, key) == getattr(other, key)
                   for key in ("words", "anchors", "forms", "images", "select_meta"))


def validated_website_receipt(path: Path = V2_RECEIPT) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            sha(path) == V2_RECEIPT_SHA
            and data.get("schema_version") == "empire.website.flagship_v2_atomic_publication_receipt.v1"
            and data.get("status") == "EXACT_APPROVED_V2_WEBSITE_PUBLICATION_VERIFIED"
            and data.get("founder_approved_inventory_sha256") == V2_INVENTORY_SHA
            and data.get("private_source_receipt_sha256") == V2_MANIFEST_SHA
            and data.get("public_files_modified") is True
            and data.get("new_public_file_count") == 632
            and data.get("payment_activation_changed") is False
            and data.get("outbound_activated") is False
            and data.get("unapproved_content_activation") is False
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def review(
    *,
    root: Path = ROOT,
    site: Path = SITE,
    reviewed: Path = REVIEWED_ROOFING,
    receipt: Path = V2_RECEIPT,
    manifest: Path = V2_MANIFEST,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        checks["reviewed_source_pinned"] = (
            sha(root / "templates/lead_smart/roofing/page.tsx") == FROZEN_APPROVED_SOURCE_SHA
        )
        checks["active_source_pinned"] = (
            sha(root / "apps/empire-public-site/src/app/roofing/page.tsx") == FROZEN_SOURCE_SHA
        )
        checks["old_reviewed_html_pinned"] = sha(reviewed) == REVIEWED_HTML_SHA
        checks["exact_v2_html_pinned"] = sha(site / "roofing.html") == V2_HTML_SHA
        checks["v2_manifest_pinned"] = sha(manifest) == V2_MANIFEST_SHA
        checks["v2_manifest_roofing_identical"] = (
            json.loads(manifest.read_text(encoding="utf-8"))
            .get("static_file_sha256", {}).get("roofing.html") == V2_HTML_SHA
        )
        checks["v2_root_publication_receipt_verified"] = validated_website_receipt(receipt)
        old = ConsumerDOM.of(reviewed.read_bytes())
        new = ConsumerDOM.of((site / "roofing.html").read_bytes())
        checks["buyer_visible_copy_and_form_semantics_unchanged"] = old.equivalent(new)
        checks["no_direct_dial_link"] = (
            not any(str(link[0]).startswith("tel:") for link in new.anchors)
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    all_ok = len(checks) == 9 and all(checks.values())
    return {
        "schema_version": SCHEMA,
        "status": "EXACT_FOUNDER_V2_WITH_REVIEWED_CONSUMER_CONTENT"
                  if all_ok else "V2_LANDING_UNVERIFIED_HELD",
        "checks": checks,
        "all_compatibility_checks_passed": all_ok,
        "v2_html_sha256": V2_HTML_SHA,
        "v2_release_receipt_sha256": V2_RECEIPT_SHA,
        "v2_founder_inventory_sha256": V2_INVENTORY_SHA,
        "scope": "LANDING_CONTENT_COMPATIBILITY_ONLY",
        "call_activation_authorized": False,
        "legal_compliance_certified": False,
        "buyer_call_route_independently_verified": False,
        "new_advertising_or_outbound_authorized": False,
        "revenue_verified": False,
        "writes": False,
    }


def accept_installed_attestation(path: Path = RUNTIME_ATTESTATION) -> bool:
    # Root-owned /etc path cannot be swapped by the unprivileged gateway user.
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o022:
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            data.get("schema_version") == SCHEMA
            and data.get("status") == "EXACT_FOUNDER_V2_WITH_REVIEWED_CONSUMER_CONTENT"
            and data.get("all_compatibility_checks_passed") is True
            and data.get("checks") is not None
            and set(data["checks"]) == {
                "reviewed_source_pinned", "active_source_pinned",
                "old_reviewed_html_pinned", "exact_v2_html_pinned",
                "v2_manifest_pinned", "v2_manifest_roofing_identical",
                "v2_root_publication_receipt_verified",
                "buyer_visible_copy_and_form_semantics_unchanged",
                "no_direct_dial_link",
            }
            and all(v is True for v in data["checks"].values())
            and data.get("scope") == "LANDING_CONTENT_COMPATIBILITY_ONLY"
            and data.get("v2_html_sha256") == V2_HTML_SHA
            and data.get("v2_release_receipt_sha256") == V2_RECEIPT_SHA
            and data.get("v2_founder_inventory_sha256") == V2_INVENTORY_SHA
            and data.get("call_activation_authorized") is False
            and data.get("legal_compliance_certified") is False
            and data.get("buyer_call_route_independently_verified") is False
            and data.get("new_advertising_or_outbound_authorized") is False
            and data.get("revenue_verified") is False
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


if __name__ == "__main__":
    import json
    import sys
    data = review()
    print(json.dumps(data, sort_keys=True))
    sys.exit(0 if data["all_compatibility_checks_passed"] else 2)
