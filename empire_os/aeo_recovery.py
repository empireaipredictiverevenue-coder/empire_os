"""Governed recovery audit for the legacy AEO metro page estate."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_META_DESC = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
    re.I | re.S,
)
_CANONICAL = re.compile(
    r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']',
    re.I | re.S,
)
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dynamic_lead_count_claim", re.compile(r"\b\d+\s+leads?\s+today\b", re.I)),
    ("live_data_claim", re.compile(r"\bpulled\s+live\b|\bfresh\s+every\s+day\b", re.I)),
    ("update_frequency_claim", re.compile(r"\bupdated\s+every\s+\d+\s+hours?\b", re.I)),
    ("unverified_fixed_price", re.compile(r"\$\s*\d+(?:\.\d+)?\s*/\s*mo\b", re.I)),
    ("speed_guarantee", re.compile(r"\bwithin\s+(?:\d+|the)\s+(?:seconds?|minutes?|hour)\b", re.I)),
    ("exclusive_lead_claim", re.compile(r"\bexclusive\s+leads?\b|\bsent\s+to\s+exactly\s+one\s+agency\b", re.I)),
    ("retired_direct_endpoint", re.compile(r"/v1/leads/direct", re.I)),
    ("placeholder_content", re.compile(r"\{\{|lorem\s+ipsum|TODO", re.I)),
)


@dataclass(frozen=True)
class AeoAssetAudit:
    path: str
    niche: str
    metro: str
    bytes: int
    text_chars: int
    title_present: bool
    meta_description_present: bool
    canonical_present: bool
    h1_present: bool
    json_ld_present: bool
    form_present: bool
    content_hash: str
    risk_flags: tuple[str, ...]
    status: str
    publish_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_aeo_asset(path: Path, *, root: Path) -> AeoAssetAudit:
    html = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(root)
    parts = rel.parts
    niche = parts[0] if parts else ""
    metro = parts[1] if len(parts) > 1 else ""
    plain = _WS.sub(" ", _TAGS.sub(" ", html)).strip()
    flags = tuple(
        name for name, pattern in RISK_PATTERNS if pattern.search(html)
    )
    structure_ok = all((
        bool(_TITLE.search(html)),
        bool(_META_DESC.search(html)),
        bool(_CANONICAL.search(html)),
        bool(_H1.search(html)),
        'application/ld+json' in html.lower(),
    ))
    if flags:
        status = "blocked_for_rewrite"
    elif not structure_ok or len(plain) < 500:
        status = "needs_quality_review"
    else:
        status = "structure_ready_for_evidence_review"

    normalized = re.sub(r"\s+", " ", html).strip().encode("utf-8")
    return AeoAssetAudit(
        path=str(rel),
        niche=niche,
        metro=metro,
        bytes=len(html.encode("utf-8")),
        text_chars=len(plain),
        title_present=bool(_TITLE.search(html)),
        meta_description_present=bool(_META_DESC.search(html)),
        canonical_present=bool(_CANONICAL.search(html)),
        h1_present=bool(_H1.search(html)),
        json_ld_present='application/ld+json' in html.lower(),
        form_present="<form" in html.lower(),
        content_hash=hashlib.sha256(normalized).hexdigest(),
        risk_flags=flags,
        status=status,
    )


def build_aeo_recovery_census(root: Path) -> dict[str, Any]:
    assets = [
        audit_aeo_asset(path, root=root)
        for path in sorted(root.glob("*/*/index.html"))
    ]
    statuses: dict[str, int] = {}
    risks: dict[str, int] = {}
    for asset in assets:
        statuses[asset.status] = statuses.get(asset.status, 0) + 1
        for flag in asset.risk_flags:
            risks[flag] = risks.get(flag, 0) + 1

    return {
        "schema_version": "empire.aeo_recovery.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "publishing_authority": False,
        "indexation_authority": False,
        "asset_count": len(assets),
        "niche_count": len({asset.niche for asset in assets}),
        "metro_count": len({asset.metro for asset in assets}),
        "unique_content_hashes": len({asset.content_hash for asset in assets}),
        "status_counts": dict(sorted(statuses.items())),
        "risk_counts": dict(sorted(risks.items())),
        "assets": [asset.as_dict() for asset in assets],
    }
