"""Observed backlink/authority graph evidence for Search Intelligence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class BacklinkObservation:
    source_url: str
    target_url: str
    observed_at: str
    anchor_text: str | None = None
    rel: str | None = None
    source: str = "observed_backlink"
    provenance: tuple[str, ...] = ()

    def validate(self) -> None:
        for name, value in (
            ("source_url", self.source_url),
            ("target_url", self.target_url),
            ("observed_at", self.observed_at),
            ("source", self.source),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        for name, value in (
            ("source_url", self.source_url),
            ("target_url", self.target_url),
        ):
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{name} must be absolute http(s)")
        if not self.provenance:
            raise ValueError("backlink observation requires provenance")

    @property
    def source_domain(self) -> str:
        return (urlparse(self.source_url).hostname or "").lower()

    @property
    def target_domain(self) -> str:
        return (urlparse(self.target_url).hostname or "").lower()

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class BacklinkGraphAnalysis:
    available: bool
    observed_backlinks: int
    referring_domains: int
    dofollow_backlinks: int
    nofollow_backlinks: int
    source_domains: tuple[str, ...]
    evidence_count: int
    reason: str | None = None
    authority_score: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyse_backlink_graph(
    observations: tuple[BacklinkObservation, ...],
    *,
    empire_domains: tuple[str, ...],
) -> BacklinkGraphAnalysis:
    domains = {
        item.strip().lower().removeprefix("www.")
        for item in empire_domains
        if item.strip()
    }
    if not domains:
        raise ValueError("at least one Empire domain required")

    for observation in observations:
        observation.validate()

    matching = tuple(
        item
        for item in observations
        if item.target_domain.removeprefix("www.") in domains
    )
    if not matching:
        return BacklinkGraphAnalysis(
            available=False,
            observed_backlinks=0,
            referring_domains=0,
            dofollow_backlinks=0,
            nofollow_backlinks=0,
            source_domains=(),
            evidence_count=0,
            reason="no_observed_backlink_evidence",
        )
    nofollow = sum(
        "nofollow" in str(item.rel or "").lower().split()
        for item in matching
    )
    dofollow = len(matching) - nofollow
    source_domains = tuple(sorted({
        item.source_domain.removeprefix("www.")
        for item in matching
    }))
    return BacklinkGraphAnalysis(
        available=True,
        observed_backlinks=len(matching),
        referring_domains=len(source_domains),
        dofollow_backlinks=dofollow,
        nofollow_backlinks=nofollow,
        source_domains=source_domains,
        evidence_count=sum(len(item.provenance) for item in matching),
        authority_score=None,
    )
