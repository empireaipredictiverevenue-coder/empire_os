"""Read-only exact provenance for reviewed 21 Oct commercial first-paint overlay.

Does not repin the base V2 release or approve new campaigns/content.
Every original V2 byte except the commercial page must remain unchanged.
The thirteen reviewed immutable assets must match their individual pins.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

SCHEMA = "empire.website.flagship_checkout_full_export_union.v1"
BASE_INVENTORY = "650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3"
NEW_COMMERCIAL_SHA = "404d87e3c3ee366415662389992c0001eb25e0bcf24e526ef898b1f0e5f2e03e"
OWNER_STAGE = Path(
    "/home/ubuntu/empire_worktrees/brokerage_current_flagship_first_paint_fix_20261021"
    "/apps/empire-public-site/out"
)
APPROVED_ADDITIONS = {
    "_next/static/chunks/418-35fd6ce1c9375243.js": "117b02704741350cff29af20879e26b60dad766d8d7653a6e7623d51c8c26d10",
    "_next/static/chunks/857.16a04c7309633386.js": "2c1df8adcbd3088fb51f309d08ad56af285506faa5a78c54141e18dcd22c004d",
    "_next/static/chunks/app/buy/page-275413c1b636985f.js": "62186e851b60ba5a0451a9b55f5ee17692e9b222c370894115e32762f4cddbba",
    "_next/static/chunks/app/commercial/page-15bf15a567b95b38.js": "5c4d6f0f8ea052858a03a86ac1688a137992bf18e6ed58d4fd89d67f18fbdb4a",
    "_next/static/chunks/app/layout-671057dcfb3abe61.js": "fed166978b5329328630779b57fd2f592d6115398aab9e4c90a6766e7b53be92",
    "_next/static/chunks/app/page-e41d0cf4c095e21e.js": "95d26ff4d04621e033703a33d4d0c819288251da8fe270934961ca56938c08c0",
    "_next/static/chunks/app/predictive-revenue/page-4e1dbfe0098fb0ca.js": "9b7498c300619ad2f0ca788a6bd8b3398a56754c5a8e5eb65478c438d90b6a1f",
    "_next/static/chunks/app/roofing/page-34bb9e7a8af82f7a.js": "00dc227900873078a7d88f2490ad61eee9fb345da42bbc9d460d713502668ab6",
    "_next/static/chunks/webpack-86a453c728ce5eda.js": "fb9b01c198149b1bdb3714c5048238e24cbb8666831a75bb5536801fcfb27fc8",
    "_next/static/css/0a5095c952ca5141.css": "8323bb5046b3ee6b6aadeb0dbf2f9f8aa5d4af96d6945846d993f601c88a488d",
    "_next/static/css/f5920ee410e18b6e.css": "343515d75833f1c4dadb76d8ff761a0596f56a661d79a9a0f4f8cd6ba7b18189",
    "_next/static/zpqETfqHpNBycZ4oCLgVa/_buildManifest.js": "30a7124443cbcb849813358902c7dc5c5f85865595b86ad936e1a97370c2c740",
    "_next/static/zpqETfqHpNBycZ4oCLgVa/_ssgManifest.js": "6d06ccc429b812337889f08fcf4e0792b070203e38a72b4af351e6506f914ad4",
}


def exact_v2_plus_reviewed_brokerage(
    *, site: Path, receipt: Path, stage: Path = OWNER_STAGE,
) -> bool:
    try:
        if (
            site.is_symlink() or not site.is_dir()
            or receipt.is_symlink() or not receipt.is_file()
            or receipt.stat().st_size > 250_000
        ):
            return False
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != SCHEMA
            or data.get("status") != "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED"
            or data.get("candidate_integrity_verified") is not True
            or data.get("new_public_release_authorized") is not False
            or data.get("public_files_modified") is not False
        ):
            return False
        original = data.get("static_file_sha256")
        if not isinstance(original, dict) or len(original) != 632:
            return False
        checksum = sha256(
            json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if checksum != BASE_INVENTORY or len(APPROVED_ADDITIONS) != 13:
            return False
        if (
            sha256((stage / "commercial.html").read_bytes()).hexdigest()
            != NEW_COMMERCIAL_SHA
        ):
            return False
        expected = dict(original)
        expected["commercial.html"] = NEW_COMMERCIAL_SHA
        for path, digest in APPROVED_ADDITIONS.items():
            if path in original or not path.startswith("_next/static/"):
                return False
            staged = stage / path
            if staged.is_symlink() or not staged.is_file():
                return False
            if sha256(staged.read_bytes()).hexdigest() != digest:
                return False
            expected[path] = digest
        # No wildcard or basename matching: the full route/file tree must be
        # exactly the base V2 set plus 13 strictly pinned files.
        found: set[str] = set()
        total = 0
        for file in site.rglob("*"):
            if file.is_symlink():
                return False
            if file.is_dir():
                continue
            if not file.is_file():
                return False
            relative = file.relative_to(site).as_posix()
            if relative not in expected or relative in found:
                return False
            found.add(relative)
            digest = sha256()
            with file.open("rb") as f:
                while (chunk := f.read(65_536)):
                    total += len(chunk)
                    if total > 300_000_000:
                        return False
                    digest.update(chunk)
            if digest.hexdigest() != expected[relative]:
                return False
        return len(found) == 645 and found == set(expected)
    except (OSError, ValueError, TypeError, OverflowError):
        return False
