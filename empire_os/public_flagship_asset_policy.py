"""Exact reviewed flagship public-asset admission. No directory exposure.

The static website release separately installs candidate assets into SITE_OUT.
Only byte-pinned, explicitly reviewed files become public via this contract.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple


class ReviewedAsset(NamedTuple):
    relative_path: str
    content_type: str
    sha256: str
    max_bytes: int


# Pin reviewed ASTRA export assets, not arbitrary paths or globs. Altering any
# of these requires a new explicit release evidence review and asset tests.
FLAGSHIP_ASSETS: dict[str, ReviewedAsset] = {
    "/brand/empire-ai-official-brand-logo-lockup.png": ReviewedAsset(
        "brand/empire-ai-official-brand-logo-lockup.png", "image/png",
        "a89c4e6c179e6fdeb5ae1e5b140d1c6007a4f359d633f51390a9fc7a1f79a64c", 400_000),
    "/art/earth-detail-v2.webp": ReviewedAsset(
        "art/earth-detail-v2.webp", "image/webp",
        "23f26c12f9cdf0b2333283870f8a303a0ade1f98161c2eb60e25692353c68b94", 600_000),
    "/art/earth/credits.html": ReviewedAsset(
        "art/earth/credits.html", "text/html",
        "1f1a6d9a17f22d99599a646c5bc4030e8f1350a3f8efa2f2b44a87ab01d48c4a", 10_000),
    "/fonts/satoshi-400.woff2": ReviewedAsset(
        "fonts/satoshi-400.woff2", "font/woff2",
        "50dca57f0b77918e0fb7dac998c3f5ef6b0c2a29657da97658a04f98ac532fc5", 50_000),
    "/fonts/satoshi-500.woff2": ReviewedAsset(
        "fonts/satoshi-500.woff2", "font/woff2",
        "af02a72246f53ad49c44a591921edbd39ec8258a03d8cc2e0532aa1e497e85b4", 50_000),
    "/fonts/satoshi-700.woff2": ReviewedAsset(
        "fonts/satoshi-700.woff2", "font/woff2",
        "353a7fbfb4475f0c31470a7449226006cb64211c71055ca9db860a8acdaa9f68", 50_000),
}


def reviewed_flagship_asset_path(route: str, site_out: Path) -> tuple[Path, str] | None:
    """Return only a matching regular, byte-pinned artifact under SITE_OUT."""
    spec = FLAGSHIP_ASSETS.get(route)
    if spec is None or site_out.is_symlink() or not site_out.is_dir():
        return None
    path = site_out / spec.relative_path
    for parent in (path, *path.parents):
        if parent == site_out:
            break
        if parent.is_symlink():
            return None
    if not path.is_file() or path.is_symlink():
        return None
    stat = path.stat()
    if stat.st_size <= 0 or stat.st_size > spec.max_bytes:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != spec.sha256:
        return None
    return path, spec.content_type
