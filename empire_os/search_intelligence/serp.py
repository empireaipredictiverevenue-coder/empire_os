"""Evidence-preserving SERP snapshots backed by Search Fabric."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from empire_os.search_fabric.search import search as search_fabric_search


class SerpSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class SerpResultEvidence:
    title: str
    url: str
    snippet: str
    position: int
    engine: str
    relevance_score: float | None
    provenance: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SerpSnapshot:
    query: str
    observed_at: str
    engine: str
    quality_gate: str | None
    cache: bool | None
    available: bool
    results: tuple[SerpResultEvidence, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["results"] = [
            result.as_dict() for result in self.results
        ]
        return data


class SearchFabricSerpAdapter:
    def __init__(
        self,
        search_fn: Callable[..., Mapping[str, Any]] = search_fabric_search,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._search = search_fn
        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def snapshot(
        self,
        query: str,
        *,
        num: int = 10,
        engine: str | None = None,
    ) -> SerpSnapshot:
        clean_query = str(query or "").strip()
        if not clean_query:
            raise SerpSnapshotError("SERP query required")

        requested = max(1, min(int(num), 20))
        if engine is None:
            response = self._search(
                clean_query,
                num=requested,
            )
        else:
            response = self._search(
                clean_query,
                num=requested,
                engine=engine,
            )
        if not isinstance(response, Mapping):
            raise SerpSnapshotError(
                "Search Fabric returned invalid payload"
            )

        params = response.get("searchParameters")
        if not isinstance(params, Mapping):
            params = {}
        engine_used = str(
            params.get("engine") or "none"
        ).strip() or "none"
        quality_gate = (
            str(params.get("quality_gate")).strip()
            if params.get("quality_gate") is not None
            else None
        )
        cache = (
            bool(params.get("cache"))
            if "cache" in params
            else None
        )

        evidence: list[SerpResultEvidence] = []
        organic = response.get("organic")
        if isinstance(organic, Sequence) and not isinstance(
            organic, (str, bytes)
        ):
            for raw in organic:
                if not isinstance(raw, Mapping):
                    continue
                url = str(raw.get("link") or "").strip()
                title = str(raw.get("title") or "").strip()
                position = raw.get("position")
                if not url or not title:
                    continue
                if not isinstance(position, int) or position < 1:
                    # Never fabricate a ranking position.
                    continue
                relevance = raw.get("relevance_score")
                try:
                    relevance_score = (
                        float(relevance)
                        if relevance is not None
                        else None
                    )
                except (TypeError, ValueError):
                    relevance_score = None

                provenance = [
                    "search_fabric",
                    f"engine:{engine_used}",
                ]
                if quality_gate:
                    provenance.append(
                        f"quality_gate:{quality_gate}"
                    )
                if cache is not None:
                    provenance.append(
                        f"cache:{str(cache).lower()}"
                    )

                evidence.append(SerpResultEvidence(
                    title=title,
                    url=url,
                    snippet=str(
                        raw.get("snippet") or ""
                    ).strip(),
                    position=position,
                    engine=engine_used,
                    relevance_score=relevance_score,
                    provenance=tuple(provenance),
                ))

        error = response.get("error")
        observed_at = self._clock().astimezone(
            timezone.utc
        ).isoformat()
        return SerpSnapshot(
            query=clean_query,
            observed_at=observed_at,
            engine=engine_used,
            quality_gate=quality_gate,
            cache=cache,
            available=bool(evidence),
            results=tuple(evidence),
            error=str(error) if error else None,
        )
