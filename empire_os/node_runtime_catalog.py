from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from empire_os.hybrid_compute import Route
from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


CATALOG_VERSION = "empire-node-runtime-catalog-v1"


@dataclass(frozen=True)
class ProbeResult:
    healthy: bool
    status_code: int | None
    endpoint: str
    error: str | None = None


Probe = Callable[[str], ProbeResult]


def probe_http(endpoint: str) -> ProbeResult:
    request = Request(
        endpoint,
        headers={
            "User-Agent": "EmpireOS-NodeFabric/1.0",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=2.0) as response:
            code = int(response.status)

            # Consume only a bounded amount. Health probing must never
            # pull arbitrary provider output into the control plane.
            response.read(4096)

            return ProbeResult(
                healthy=200 <= code < 300,
                status_code=code,
                endpoint=endpoint,
            )

    except HTTPError as exc:
        return ProbeResult(
            healthy=False,
            status_code=int(exc.code),
            endpoint=endpoint,
            error=f"http_{exc.code}",
        )

    except (URLError, TimeoutError, OSError) as exc:
        return ProbeResult(
            healthy=False,
            status_code=None,
            endpoint=endpoint,
            error=type(exc).__name__,
        )


def _health(result: ProbeResult) -> NodeHealth:
    return (
        NodeHealth.HEALTHY
        if result.healthy
        else NodeHealth.OFFLINE
    )


def build_runtime_registry(
    *,
    probe: Probe = probe_http,
) -> NodeRegistry:
    registry = NodeRegistry()

    laya = probe(
        "http://127.0.0.1:8769/health"
    )

    registry.register(
        NodeSpec(
            node_id="laya-shadow-system1",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(
                {
                    "compute.local.small",
                    "inference.system1",
                    "decision.typed.shadow",
                }
            ),
            routes=frozenset(
                {Route.LOCAL_SMALL}
            ),
            health=_health(laya),
            authority=NodeAuthority.OBSERVE,
            provider="laya",
            endpoint=laya.endpoint,
            metadata={
                "probe_status_code": laya.status_code,
                "probe_error": laya.error,
                "execution_enabled": False,
                "shadow_only": True,
            },
        )
    )

    llama = probe(
        "http://127.0.0.1:11435/health"
    )

    registry.register(
        NodeSpec(
            node_id="qwen25-coder-1_5b",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(
                {
                    "compute.local.small",
                    "inference.coder",
                }
            ),
            routes=frozenset(
                {Route.LOCAL_SMALL}
            ),
            health=_health(llama),
            authority=NodeAuthority.OBSERVE,
            provider="llama.cpp",
            endpoint=llama.endpoint,
            metadata={
                "model_family": "qwen2.5-coder",
                "declared_size": "1.5b",
                "probe_status_code": (
                    llama.status_code
                ),
                "probe_error": llama.error,
                "execution_enabled": False,
            },
        )
    )

    ollama = probe(
        "http://127.0.0.1:11434/api/tags"
    )

    # Ollama is deliberately NOT assigned LOCAL_STRONG yet.
    # A reachable process is not evidence that an installed model
    # meets the quality threshold for that route.
    registry.register(
        NodeSpec(
            node_id="ollama-local-pool",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(
                {
                    "inference.local.pool",
                }
            ),
            routes=frozenset(),
            health=_health(ollama),
            authority=NodeAuthority.OBSERVE,
            provider="ollama",
            endpoint=ollama.endpoint,
            metadata={
                "probe_status_code": (
                    ollama.status_code
                ),
                "probe_error": ollama.error,
                "route_classification": (
                    "unverified"
                ),
                "execution_enabled": False,
            },
        )
    )

    return registry


def runtime_snapshot(
    *,
    probe: Probe = probe_http,
) -> dict:
    registry = build_runtime_registry(
        probe=probe
    )

    snapshot = registry.snapshot()

    snapshot["catalog_version"] = (
        CATALOG_VERSION
    )

    snapshot["classification"] = {
        "local_small_candidates": [
            node.node_id
            for node in registry.candidates(
                capability="compute.local.small",
                route=Route.LOCAL_SMALL,
            )
        ],
        "local_strong_candidates": [
            node.node_id
            for node in registry.candidates(
                capability="compute.local.strong",
                route=Route.LOCAL_STRONG,
            )
        ],
        "unclassified_local_pools": [
            node.node_id
            for node in registry.all()
            if (
                "inference.local.pool"
                in node.capabilities
            )
        ],
    }

    return snapshot


def main() -> int:
    print(
        json.dumps(
            runtime_snapshot(),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
