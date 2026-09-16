"""Empire Search Fabric engine registry and normalized contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    position: int = 0

    engine: str = ""
    query: str = ""

    relevance_score: float = 0.0
    geo_score: float = 0.0
    entity_score: float = 0.0
    consensus_score: float = 0.0
    confidence_score: float = 0.0
    result_type: str = "unknown"

    provenance: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineHealth:
    name: str

    enabled: bool = True
    automatic: bool = True

    healthy: bool = True
    consecutive_failures: int = 0

    queries: int = 0
    successes: int = 0
    rejected: int = 0

    last_error: str = ""

    @property
    def success_rate(self) -> float:
        if not self.queries:
            return 0.0
        return self.successes / self.queries


@dataclass
class SearchEngine:
    name: str
    mode: str

    requires_key: bool = False
    automatic: bool = True

    country: Optional[str] = None
    language: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


ENGINES: Dict[str, SearchEngine] = {
    # Working keyless retrieval.
    "duckduckgo_html": SearchEngine(
        name="duckduckgo_html",
        mode="keyless_html",
        automatic=True,
        country="US",
        language="en",
    ),

    # Reachable but currently producing bad results.
    "bing_html": SearchEngine(
        name="bing_html",
        mode="keyless_html",
        automatic=False,
        country="US",
        language="en",
        metadata={
            "state": "quarantined",
            "reason": "irrelevant retrieval observed",
        },
    ),

    # Official Google adapter. Disabled until authorized credentials exist.
    "google_web": SearchEngine(
        name="google_web",
        mode="official_api",
        requires_key=True,
        automatic=False,
        country="US",
        language="en",
    ),

    # Optional independent index.
    "brave": SearchEngine(
        name="brave",
        mode="official_api",
        requires_key=True,
        automatic=False,
        country="US",
        language="en",
    ),

    # Additional adapters can be enabled after validation.
    "yahoo": SearchEngine(
        name="yahoo",
        mode="candidate",
        automatic=False,
    ),
    "mojeek": SearchEngine(
        name="mojeek",
        mode="candidate",
        automatic=False,
    ),
    "ecosia": SearchEngine(
        name="ecosia",
        mode="candidate",
        automatic=False,
    ),
    "qwant": SearchEngine(
        name="qwant",
        mode="candidate",
        automatic=False,
    ),
}


HEALTH: Dict[str, EngineHealth] = {
    name: EngineHealth(
        name=name,
        automatic=engine.automatic,
    )
    for name, engine in ENGINES.items()
}


def record_success(name: str) -> None:
    health = HEALTH[name]
    health.queries += 1
    health.successes += 1
    health.consecutive_failures = 0
    health.healthy = True
    health.last_error = ""


def record_rejection(name: str, reason: str) -> None:
    health = HEALTH[name]
    health.queries += 1
    health.rejected += 1
    health.consecutive_failures += 1
    health.last_error = reason

    if health.consecutive_failures >= 3:
        health.healthy = False


def active_engines() -> List[SearchEngine]:
    return [
        engine
        for name, engine in ENGINES.items()
        if (
            engine.automatic
            and HEALTH[name].enabled
            and HEALTH[name].healthy
        )
    ]
