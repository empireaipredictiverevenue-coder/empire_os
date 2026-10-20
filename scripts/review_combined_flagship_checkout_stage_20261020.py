"""Read-only attestation of ASTRA cinematic + latest checkout source stage.

A hash-matched stage is *not* production publication or visual signoff.
Do not rewrite the existing October 13 BSC checkout manifest.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path("apps/empire-public-site")
PAGES = ("index.html", "buy.html", "commercial.html")
SOURCES = (
    "src/app/page.tsx", "src/app/layout.tsx", "src/app/globals.css",
    "src/components/CinematicExperience.tsx",
    "src/components/EarthJourneyScene.tsx",
    "src/components/scroll-world-director.ts",
    "src/app/buy/page.tsx", "src/app/commercial/page.tsx",
    "src/lib/buyer-proposal-handoff.ts",
)
SCHEMA = "empire.website.flagship_checkout_source_convergence.v1"
MANIFEST = Path("docs/website/release_candidates/FLAGSHIP_CHECKOUT_COMBINED_STAGE_20261020.json")


class StaticAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: set[str] = set()
        self.external_scripts = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        path = attributes.get("src") if tag == "script" else (
            attributes.get("href") if tag == "link" else None
        )
        if tag == "script" and path and not path.startswith("/_next/static/"):
            self.external_scripts = True
        if isinstance(path, str) and path.startswith("/_next/static/"):
            path = path.split("?", 1)[0]
            if path.endswith((".js", ".css", ".woff", ".woff2")):
                self.assets.add(path.removeprefix("/"))


def _read_under(root: Path, path: str, size=10_000_000) -> bytes:
    full = root / path
    if (
        full.is_symlink() or not full.is_file()
        or not full.resolve().is_relative_to(root.resolve())
        or full.stat().st_size <= 0 or full.stat().st_size > size
    ):
        raise ValueError("unavailable_untrusted_build_input")
    return full.read_bytes()


def manifest_for_stage(*, project: Path) -> dict:
    source_hashes = {p: sha256(_read_under(project, p, 2_000_000)).hexdigest()
                     for p in SOURCES}
    html_hashes = {}
    assets = StaticAssets()
    snippets = []
    for name in PAGES:
        raw = _read_under(project / "out", name, 2_000_000)
        html_hashes[name] = sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        assets.feed(text)
        snippets.append(text)
    if assets.external_scripts or len(assets.assets) < 5:
        raise ValueError("unexpected_external_script_or_missing_bundles")
    asset_hashes = {
        path: sha256(_read_under(project / "out", path)).hexdigest()
        for path in sorted(assets.assets)
    }
    joined = "\n".join(snippets)
    compiled = b"\n".join(
        _read_under(project / "out", path) for path in sorted(assets.assets)
        if path.endswith(".js")
    )
    if not (
        "EmpireOS" in joined
        and "Intelligence Infrastructure" in joined
        and b"REQUEST A PROPOSAL INSTEAD" in compiled
        and b"/v1/checkout/commercial/offers" in compiled
        and b"The requested product is not available for a proposal" in compiled
        and "selected-product-bridge-20261020.js" not in joined
    ):
        raise ValueError("staged_product_or_cinematic_contract_unverified")
    return {
        "schema_version": SCHEMA,
        "stage_status": "COMBINED_SOURCE_BUILD_VERIFIED_AWAITING_VISUAL_RELEASE",
        "source_origin": {
            "cinematic_ast_source_commit": "084f4e80",
            "buyer_proposal_source_commit": "56817a08",
        },
        "source_sha256": source_hashes,
        "page_html_sha256": html_hashes,
        "page_asset_sha256": asset_hashes,
        "reviewed_page_count": len(html_hashes),
        "referenced_immutable_asset_count": len(asset_hashes),
        "html_preview_deployed": False,
        "existing_oct13_manifest_reapproved": False,
        "website_visual_approval": False,
        "payment_activation": False,
        "customer_enquiry_or_order_submitted": False,
        "revenue_verified": False,
        "external_actions": False,
    }


def verify(*, project: Path, pinned: Path) -> dict:
    try:
        raw = json.loads(_read_under(pinned.parent, pinned.name, 2_000_000))
        current = manifest_for_stage(project=project)
        ok = current == raw
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        ok = False
        current = {"schema_version": SCHEMA}
    return {
        "schema_version": SCHEMA,
        "status": "COMBINED_STAGED_BUILD_HASH_VERIFIED" if ok
                  else "COMBINED_STAGED_BUILD_INTEGRITY_HOLD",
        "source_and_build_match_original_pins": ok,
        "new_public_release_authorized": False,
        "buyer_order_or_email_submitted": False,
        "payment_execution": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    result = verify(project=args.project, pinned=args.manifest)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["source_and_build_match_original_pins"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
