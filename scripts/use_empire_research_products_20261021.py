"""Use Empire Research or Empire Agent from the existing EmpireOS worktree.

Example:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.use_empire_research_products_20261021 \
 --read-only --product empire_research --country both --niche dental \
 --depth quality --save-private

Saved receipts remain restricted owner-only internal artifacts; not sales assets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

from empire_os.research.research_products import (
    PRODUCTS, product_catalog, use_product
)

DEFAULT_RECEIPTS = Path(
    "/home/ubuntu/.local/share/empire-research-products"
)


def save_private_result(report: dict, *, directory: Path = DEFAULT_RECEIPTS) -> Path:
    """Exclusive receipt file; never overwrite another run or allow symlinks."""
    import hashlib
    if report.get("schema_version") != "empire.research.product_result.v1":
        raise ValueError("PROVENANCE_PRODUCT_RECEIPT_REQUIRED")
    dir_path = Path(directory)
    if dir_path.is_symlink():
        raise ValueError("UNTRUSTED_RECEIPT_DIRECTORY_SYMLINK")
    dir_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(dir_path.stat().st_mode) != 0o700:
        raise ValueError("PRIVATE_RECEIPT_DIRECTORY_MUST_BE_OWNER_ONLY")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    name = (
        report["product_id"] + "-" + report["niche"] + "-" +
        report["market"] + "-" + digest[:20] + ".json"
    )
    target = dir_path / name
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized + "\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--read-only", action="store_true", required=True)
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--product", choices=tuple(PRODUCTS))
    ap.add_argument("--country", choices=("US", "GB", "both"), default="both")
    ap.add_argument("--niche", choices=("dental", "roofing", "solar",
                                       "hvac", "legal", "property"), default="dental")
    ap.add_argument("--depth", choices=("speed", "balanced", "quality"), default="quality")
    ap.add_argument("--save-private", action="store_true")
    args = ap.parse_args(argv)
    if args.catalog:
        print(json.dumps(product_catalog(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if not args.product:
        ap.error("--product required unless --catalog")
    report = use_product(args.product, country=args.country, niche=args.niche,
                         depth=args.depth)
    if args.save_private:
        path = save_private_result(report)
        report = {**report, "private_receipt_path": str(path)}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] in (
        "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING",
        "WORK_COMPLETED_FOR_EDITORIAL_REVIEW"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
