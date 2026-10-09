from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import socket
from typing import Any
from urllib.parse import urlparse


FILE_SUFFIXES = {
    "json", "md", "txt", "py", "sql",
    "yaml", "yml", "csv", "log",
    "php", "aspx", "asp", "jsp", "xml",
}


KNOWN_NON_TARGETS = {
    "ahrefs.com",
    "semrush.com",
    "serpapi.com",
    "localfalcon.com",
    "aol.com",
}


@dataclass(frozen=True)
class EntityTypeDecision:
    raw: str
    canonical: str | None
    entity_type: str
    confidence: float
    reason: str
    lane_allowed: bool
    quarantine: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize(value: str) -> str:
    value = (value or "").strip().lower()

    if "://" in value:
        try:
            value = urlparse(value).hostname or value
        except Exception:
            pass

    value = value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    value = value.rstrip(".")

    if value.startswith("www."):
        value = value[4:]

    return value


def syntactic_domain(value: str) -> bool:
    domain = normalize(value)

    if not domain or "." not in domain:
        return False

    labels = domain.split(".")

    if len(labels) < 2:
        return False

    final = labels[-1]

    if not re.fullmatch(
        r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})",
        final,
    ):
        return False

    for label in labels:
        if not label:
            return False

        if len(label) > 63:
            return False

        if label.startswith("-") or label.endswith("-"):
            return False

        if not re.fullmatch(
            r"[a-z0-9-]+",
            label,
        ):
            return False

    return True


def file_or_path_artifact(value: str) -> bool:
    raw = (value or "").strip().lower()

    if "/" in raw or "\\" in raw:
        return True

    if "." not in raw:
        return False

    suffix = raw.rsplit(".", 1)[-1]

    return suffix in FILE_SUFFIXES


def internal_token(value: str) -> bool:
    value = normalize(value)

    return (
        value.startswith("empire.")
        or value.startswith("runtime.")
        or value.startswith("internal.")
    )


def dns_resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(
            domain,
            443,
            type=socket.SOCK_STREAM,
        )
        return True
    except Exception:
        return False


def looks_person_like(value: str) -> bool:
    value = normalize(value)

    labels = value.split(".")

    if len(labels) != 2:
        return False

    left, right = labels

    if not left.isalpha() or not right.isalpha():
        return False

    return (
        2 <= len(left) <= 24
        and 2 <= len(right) <= 24
    )


def classify(
    value: str,
    *,
    direct_site_success: bool = False,
    known_non_targets: set[str] | None = None,
    resolve_dns: bool = True,
) -> EntityTypeDecision:

    known_non_targets = (
        known_non_targets
        or KNOWN_NON_TARGETS
    )

    canonical = normalize(value)

    if not canonical:
        return EntityTypeDecision(
            raw=value,
            canonical=None,
            entity_type="INVALID",
            confidence=1.0,
            reason="empty_identity",
            lane_allowed=False,
            quarantine=True,
        )

    if internal_token(canonical):
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="INTERNAL_TOKEN",
            confidence=1.0,
            reason="internal_namespace",
            lane_allowed=False,
            quarantine=True,
        )

    if file_or_path_artifact(value):
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="FILE_OR_PATH",
            confidence=1.0,
            reason="file_or_framework_artifact",
            lane_allowed=False,
            quarantine=True,
        )

    if canonical in known_non_targets:
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="KNOWN_NON_TARGET",
            confidence=1.0,
            reason="known_tool_or_non_target",
            lane_allowed=False,
            quarantine=True,
        )

    if not syntactic_domain(canonical):
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="INVALID",
            confidence=0.99,
            reason="invalid_domain_structure",
            lane_allowed=False,
            quarantine=True,
        )

    if direct_site_success:
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="PUBLIC_DOMAIN",
            confidence=1.0,
            reason="direct_site_success",
            lane_allowed=True,
            quarantine=False,
        )

    if resolve_dns and dns_resolves(canonical):
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="PUBLIC_DOMAIN",
            confidence=0.98,
            reason="dns_resolution",
            lane_allowed=True,
            quarantine=False,
        )

    if looks_person_like(canonical):
        return EntityTypeDecision(
            raw=value,
            canonical=canonical,
            entity_type="PERSON_LIKE_OR_UNKNOWN",
            confidence=0.75,
            reason="person_like_token_without_domain_proof",
            lane_allowed=False,
            quarantine=True,
        )

    return EntityTypeDecision(
        raw=value,
        canonical=canonical,
        entity_type="DOMAIN_UNVERIFIED",
        confidence=0.60,
        reason="valid_domain_syntax_without_runtime_proof",
        lane_allowed=False,
        quarantine=True,
    )
