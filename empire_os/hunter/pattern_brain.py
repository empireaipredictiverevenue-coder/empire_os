"""Company-specific email pattern learning for Empire Hunter."""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Mapping
from urllib.parse import urlparse

from empire_os.hunter.models import DomainPattern


PATTERNS = (
    "first.last",
    "firstlast",
    "f.last",
    "flast",
    "firstl",
    "first",
    "last",
)


def normalize_domain(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").lower()
    return host.removeprefix("www.")


def _name_parts(person_name: str) -> tuple[str, str]:
    parts = [
        re.sub(r"[^a-z]", "", value.lower())
        for value in str(person_name or "").replace("-", " ").split()
    ]
    parts = [value for value in parts if value]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[-1]


def render_pattern(pattern: str, first: str, last: str) -> str:
    mapping = {
        "first.last": f"{first}.{last}",
        "firstlast": f"{first}{last}",
        "f.last": f"{first[:1]}.{last}",
        "flast": f"{first[:1]}{last}",
        "firstl": f"{first}{last[:1]}",
        "first": first,
        "last": last,
    }
    if pattern not in mapping:
        raise ValueError(f"unsupported email pattern: {pattern}")
    return mapping[pattern]


def infer_pattern(
    email: str,
    person_name: str,
    *,
    domain: str | None = None,
) -> str | None:
    raw = str(email or "").strip().lower()
    if "@" not in raw:
        return None
    local, email_domain = raw.rsplit("@", 1)
    expected_domain = normalize_domain(domain or email_domain)
    if normalize_domain(email_domain) != expected_domain:
        return None

    first, last = _name_parts(person_name)
    if not first or not last:
        return None

    for pattern in PATTERNS:
        if local == render_pattern(pattern, first, last):
            return pattern
    return None


def learn_domain_pattern(
    observations: Iterable[Mapping[str, object]],
    *,
    domain: str,
) -> DomainPattern:
    host = normalize_domain(domain)
    inferred: list[str] = []
    for row in observations:
        if row.get("person_bound") is not True:
            continue
        if row.get("first_party") is not True:
            continue
        pattern = infer_pattern(
            str(row.get("email") or ""),
            str(row.get("person_name") or ""),
            domain=host,
        )
        if pattern:
            inferred.append(pattern)

    if not inferred:
        return DomainPattern(
            domain=host,
            pattern=None,
            observations=0,
            agreement=0.0,
            confidence=0.0,
        )

    counts = Counter(inferred)
    pattern, wins = counts.most_common(1)[0]
    total = len(inferred)
    agreement = wins / total
    base = 0.62 if total == 1 else 0.78
    confidence = min(
        0.98,
        base + 0.12 * min(total - 1, 2) + 0.08 * (agreement - 0.5),
    )
    return DomainPattern(
        domain=host,
        pattern=pattern,
        observations=total,
        agreement=round(agreement, 4),
        confidence=round(confidence, 4),
    )


def generate_candidate(
    person_name: str,
    domain: str,
    pattern: str,
) -> str | None:
    first, last = _name_parts(person_name)
    host = normalize_domain(domain)
    if not first or not last or not host:
        return None
    return f"{render_pattern(pattern, first, last)}@{host}"
