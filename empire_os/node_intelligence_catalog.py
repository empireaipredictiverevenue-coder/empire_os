from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


CATALOG_VERSION = "empire-node-intelligence-catalog-v1"

FOUNDER_NODES_URL = (
    "http://127.0.0.1:8766/"
    "v1/founder-intelligence-nodes"
)

SEARCH_HEALTH_URL = (
    "http://127.0.0.1:8771/health"
)


FetchJson = Callable[[str], Mapping[str, Any]]


def fetch_json(url: str) -> Mapping[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "EmpireOS-NodeFabric/2.1",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=3.0) as response:
            if not 200 <= int(response.status) < 300:
                raise RuntimeError(
                    f"unexpected HTTP {response.status}"
                )

            raw = response.read(1_000_000)

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise RuntimeError(
            f"canonical read failed: {url}"
        ) from exc

    payload = json.loads(raw)

    if not isinstance(payload, Mapping):
        raise RuntimeError(
            "canonical JSON payload must be object"
        )

    return payload


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    ).strip("-")

    if not text:
        raise ValueError("canonical node key missing")

    return text


def _source_health(
    lifecycle_state: Any,
) -> NodeHealth:
    state = str(
        lifecycle_state or ""
    ).strip().lower()

    if state in {
        "active",
        "healthy",
        "live",
        "operational",
        "production",
        "ready",
        "verified",
    }:
        return NodeHealth.HEALTHY

    if state in {
        "degraded",
        "limited",
        "partial",
    }:
        return NodeHealth.DEGRADED

    if state in {
        "disabled",
        "failed",
        "offline",
        "retired",
    }:
        return NodeHealth.OFFLINE

    # Never turn an unrecognised lifecycle word into
    # production health.
    return NodeHealth.UNKNOWN


def _canonical_capabilities(
    row: Mapping[str, Any],
) -> frozenset[str]:
    key = _slug(row.get("key"))

    capabilities = {
        "intelligence.node",
        "intelligence."
        + key.replace("-", "_"),
    }

    raw = row.get("capabilities")

    if isinstance(raw, str):
        raw = [raw]

    if isinstance(raw, (list, tuple, set)):
        for value in raw:
            rendered = str(value).strip()

            if rendered:
                capabilities.add(rendered)

    return frozenset(capabilities)


def add_founder_intelligence_nodes(
    registry: NodeRegistry,
    *,
    fetch: FetchJson = fetch_json,
    url: str = FOUNDER_NODES_URL,
) -> NodeRegistry:
    payload = fetch(url)

    rows = payload.get("nodes")

    if not isinstance(rows, list):
        raise RuntimeError(
            "founder intelligence nodes missing"
        )

    if not rows:
        raise RuntimeError(
            "founder intelligence catalog empty"
        )

    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RuntimeError(
                "invalid founder intelligence node"
            )

        key = _slug(raw.get("key"))

        registry.register(
            NodeSpec(
                node_id=f"intelligence-{key}",
                kind=NodeKind.INTELLIGENCE,
                capabilities=(
                    _canonical_capabilities(raw)
                ),
                routes=frozenset(),
                health=_source_health(
                    raw.get("lifecycle_state")
                ),
                # Node Fabric V2 never inherits execution
                # authority from a read model.
                authority=NodeAuthority.OBSERVE,
                provider="empire-native",
                metadata={
                    "catalog_version": (
                        CATALOG_VERSION
                    ),
                    "canonical_key": key,
                    "canonical_name": (
                        raw.get("name")
                    ),
                    "source_lifecycle_state": (
                        raw.get("lifecycle_state")
                    ),
                    "source_execution_authority": (
                        raw.get(
                            "execution_authority"
                        )
                    ),
                    "execution_enabled": False,
                    "source": (
                        "founder-intelligence-nodes"
                    ),
                },
            )
        )

    return registry


def add_search_intelligence_node(
    registry: NodeRegistry,
    *,
    fetch: FetchJson = fetch_json,
    url: str = SEARCH_HEALTH_URL,
) -> NodeRegistry:
    try:
        payload = fetch(url)

        service_ok = payload.get("ok") is True

        observe_safe = (
            str(
                payload.get("mode") or ""
            ).upper()
            == "OBSERVE"
            and payload.get(
                "execution_allowed"
            )
            is False
        )

        health = (
            NodeHealth.HEALTHY
            if service_ok and observe_safe
            else NodeHealth.DEGRADED
        )

        metadata = {
            "catalog_version": CATALOG_VERSION,
            "service": payload.get("service"),
            "mode": payload.get("mode"),
            "source_execution_allowed": (
                payload.get(
                    "execution_allowed"
                )
            ),
            "execution_enabled": False,
            "live_health_verified": service_ok,
            "observe_boundary_verified": (
                observe_safe
            ),
        }

    except Exception as exc:
        health = NodeHealth.OFFLINE

        metadata = {
            "catalog_version": CATALOG_VERSION,
            "execution_enabled": False,
            "live_health_verified": False,
            "observe_boundary_verified": False,
            "error": type(exc).__name__,
        }

    registry.register(
        NodeSpec(
            node_id="search-intelligence-api",
            kind=NodeKind.INTELLIGENCE,
            capabilities=frozenset({
                "intelligence.node",
                "intelligence.search",
                "search.evidence",
                "search.opportunity",
                "search.competitor",
                "search.ai_visibility",
                "search.technical_audit",
            }),
            routes=frozenset(),
            health=health,
            authority=NodeAuthority.OBSERVE,
            provider="empire-native",
            endpoint=url,
            metadata=metadata,
        )
    )

    return registry


def add_intelligence_nodes(
    registry: NodeRegistry,
    *,
    fetch: FetchJson = fetch_json,
) -> NodeRegistry:
    add_founder_intelligence_nodes(
        registry,
        fetch=fetch,
    )

    add_search_intelligence_node(
        registry,
        fetch=fetch,
    )

    return registry
