"""Bounded zero-key Search Fabric recovery lane.

Production contract:
- no authenticated provider required;
- never fans out through every legacy provider;
- last-known-good search evidence is discovery-only;
- maximum two public recovery failures before persistent cooldown;
- memoizes repeated queries inside a process;
- provider failure is operational UNKNOWN, never semantic no-business;
- reserved test/documentation domains can never become evidence.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from empire_os.search_fabric.public_fallback import (
    search_public_web,
)
from empire_os.search_fabric.search import (
    _last_known_good_cache,
    _quality_filter,
    _set_cache,
)


HEALTH_PATH = Path(
    os.environ.get(
        "EMPIRE_SEARCH_HEALTH_PATH",
        "/srv/empire_os/runtime/search/provider_health_v2.json",
    )
)

MEMO_TTL_SECONDS = 900.0
FAILURE_THRESHOLD = 2
COOLDOWN_SECONDS = 2700.0

_MEMO: dict[
    tuple[str, int],
    tuple[float, dict[str, Any]],
] = {}


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _reserved_url(value: Any) -> bool:
    try:
        host = (
            urlparse(
                str(value or "")
            )
            .hostname
            or ""
        ).lower()
    except Exception:
        return True

    if not host:
        return True

    if host in {
        "localhost",
        "example.com",
        "example.org",
        "example.net",
    }:
        return True

    if (
        host.endswith(".example")
        or host.endswith(".invalid")
        or host.endswith(".test")
    ):
        return True

    return False


def _real_rows(
    rows: Any,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for raw in rows or ():
        if not isinstance(
            raw,
            dict,
        ):
            continue

        row = dict(raw)

        url = (
            row.get("link")
            or row.get("url")
        )

        if _reserved_url(url):
            continue

        result.append(row)

    return result


def _default_health() -> dict[str, Any]:
    return {
        "schema_version":
            "empire.search_provider_health.v2",
        "provider":
            "public_search_recovery",
        "consecutive_failures":
            0,
        "circuit_open_until":
            0.0,
        "last_success_at":
            None,
        "last_failure_at":
            None,
        "last_state":
            "UNKNOWN",
    }


def _load_health() -> dict[str, Any]:
    try:
        payload = json.loads(
            HEALTH_PATH.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            payload,
            dict,
        ):
            return {
                **_default_health(),
                **payload,
            }
    except Exception:
        pass

    return _default_health()


def _save_health(
    health: dict[str, Any],
) -> None:
    try:
        HEALTH_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            HEALTH_PATH.parent
            / (
                HEALTH_PATH.name
                + ".tmp"
            )
        )

        temporary.write_text(
            json.dumps(
                health,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        temporary.replace(
            HEALTH_PATH
        )
    except Exception:
        # Health persistence must never break discovery.
        pass


def _circuit_open() -> tuple[
    bool,
    dict[str, Any],
]:
    health = _load_health()

    now = time.time()

    open_until = float(
        health.get(
            "circuit_open_until"
        )
        or 0.0
    )

    if open_until > now:
        return True, health

    if open_until:
        health[
            "circuit_open_until"
        ] = 0.0

        health[
            "consecutive_failures"
        ] = 0

        health[
            "last_state"
        ] = "HALF_OPEN"

        _save_health(
            health
        )

    return False, health


def _record_success() -> None:
    health = _load_health()

    health[
        "consecutive_failures"
    ] = 0

    health[
        "circuit_open_until"
    ] = 0.0

    health[
        "last_success_at"
    ] = time.time()

    health[
        "last_state"
    ] = "HEALTHY"

    _save_health(
        health
    )


def _record_failure() -> dict[str, Any]:
    health = _load_health()

    failures = int(
        health.get(
            "consecutive_failures"
        )
        or 0
    ) + 1

    health[
        "consecutive_failures"
    ] = failures

    health[
        "last_failure_at"
    ] = time.time()

    if failures >= FAILURE_THRESHOLD:
        health[
            "circuit_open_until"
        ] = (
            time.time()
            + COOLDOWN_SECONDS
        )

        health[
            "last_state"
        ] = "CIRCUIT_OPEN"

    else:
        health[
            "last_state"
        ] = "DEGRADED"

    _save_health(
        health
    )

    return health


def _memo_get(
    query: str,
    num: int,
) -> dict[str, Any] | None:
    key = (
        query,
        num,
    )

    item = _MEMO.get(
        key
    )

    if item is None:
        return None

    observed_at, payload = item

    if (
        time.monotonic()
        - observed_at
        > MEMO_TTL_SECONDS
    ):
        _MEMO.pop(
            key,
            None,
        )

        return None

    result = dict(
        payload
    )

    params = dict(
        result.get(
            "searchParameters",
            {},
        )
    )

    params[
        "memory_cache"
    ] = True

    result[
        "searchParameters"
    ] = params

    return result


def _memo_put(
    query: str,
    num: int,
    payload: dict[str, Any],
) -> None:
    _MEMO[
        (
            query,
            num,
        )
    ] = (
        time.monotonic(),
        dict(payload),
    )


def _last_known_good(
    query: str,
    num: int,
) -> dict[str, Any] | None:
    try:
        cached = _last_known_good_cache(
            query,
            num,
        )
    except Exception:
        return None

    if not cached:
        return None

    rows = _real_rows(
        cached.get(
            "organic",
            [],
        )
    )

    rows = _quality_filter(
        rows,
        query,
        num,
    )

    if not rows:
        return None

    result = dict(
        cached
    )

    result[
        "organic"
    ] = rows

    params = dict(
        result.get(
            "searchParameters",
            {},
        )
    )

    params.update({
        "q":
            query,
        "num":
            num,
        "cache":
            True,
        "stale_cache":
            True,
        "recovery":
            True,
        "search_state":
            "STALE_RESULTS",
        "quality_gate":
            "lexical_v2",
    })

    result[
        "searchParameters"
    ] = params

    result[
        "search_operational_status"
    ] = (
        "DEGRADED_WITH_LAST_KNOWN_GOOD"
    )

    result[
        "error"
    ] = None

    return result


def _degraded(
    query: str,
    num: int,
    *,
    circuit_open: bool,
) -> dict[str, Any]:
    return {
        "organic": [],
        "searchParameters": {
            "q":
                query,
            "num":
                num,
            "engine":
                "public_recovery",
            "search_state":
                "PROVIDER_DEGRADED",
            "cache":
                False,
            "circuit_open":
                circuit_open,
        },
        "search_operational_status":
            (
                "CIRCUIT_OPEN"
                if circuit_open
                else "DEGRADED"
            ),
        "error":
            (
                "Public discovery circuit open"
                if circuit_open
                else "Public discovery unavailable"
            ),
    }


def search_reliable(
    query: str,
    num: int = 10,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Perform at most one bounded public provider attempt."""

    query = _clean(
        query
    )

    num = max(
        1,
        min(
            int(num),
            20,
        ),
    )

    if not query:
        return {
            "organic": [],
            "searchParameters": {
                "q": "",
                "num":
                    num,
                "engine":
                    "none",
                "search_state":
                    "INVALID_QUERY",
            },
            "search_operational_status":
                "HEALTHY",
            "error":
                "empty query",
        }

    memo = _memo_get(
        query,
        num,
    )

    if memo is not None:
        return memo

    # -------------------------------------------
    # 1. Reuse historical real evidence first.
    #
    # This remains discovery evidence only.
    # The first-party site probe still re-verifies.
    # -------------------------------------------

    if use_cache:
        stale = _last_known_good(
            query,
            num,
        )

        if stale:
            _memo_put(
                query,
                num,
                stale,
            )

            return stale

    # -------------------------------------------
    # 2. Persistent circuit prevents hammering.
    # -------------------------------------------

    is_open, _ = _circuit_open()

    if is_open:
        result = _degraded(
            query,
            num,
            circuit_open=True,
        )

        _memo_put(
            query,
            num,
            result,
        )

        return result

    # -------------------------------------------
    # 3. Exactly one bounded public recovery call.
    # -------------------------------------------

    try:
        raw_rows = (
            search_public_web(
                query,
                num=num,
            )
            or []
        )
    except Exception:
        raw_rows = []

    rows = _real_rows(
        raw_rows
    )

    rows = _quality_filter(
        rows,
        query,
        num,
    )

    if rows:
        _record_success()

        engine = _clean(
            rows[0].get(
                "engine"
            )
        ) or "public_recovery"

        result = {
            "organic":
                rows,
            "searchParameters": {
                "q":
                    query,
                "num":
                    num,
                "engine":
                    engine,
                "search_state":
                    "RESULTS",
                "quality_gate":
                    "lexical_v2",
                "cache":
                    False,
                "recovery":
                    True,
                "circuit_open":
                    False,
            },
            "search_operational_status":
                "RECOVERED",
            "error":
                None,
        }

        if use_cache:
            try:
                _set_cache(
                    engine,
                    query,
                    num,
                    result,
                )
            except Exception:
                pass

        _memo_put(
            query,
            num,
            result,
        )

        return result

    # -------------------------------------------
    # 4. Failed public attempt.
    # -------------------------------------------

    health = _record_failure()

    circuit_now_open = (
        float(
            health.get(
                "circuit_open_until"
            )
            or 0.0
        )
        > time.time()
    )

    # One final stale check handles another process
    # having populated evidence during this attempt.
    if use_cache:
        stale = _last_known_good(
            query,
            num,
        )

        if stale:
            _memo_put(
                query,
                num,
                stale,
            )

            return stale

    result = _degraded(
        query,
        num,
        circuit_open=
            circuit_now_open,
    )

    _memo_put(
        query,
        num,
        result,
    )

    return result


def search_reliable_rows(
    query: str,
    *,
    num: int = 8,
) -> list[dict[str, Any]]:
    result = search_reliable(
        query,
        num=num,
        use_cache=True,
    )

    return [
        dict(row)
        for row in (
            result.get(
                "organic",
                [],
            )
            or []
        )
        if isinstance(
            row,
            dict,
        )
    ]


def provider_health() -> dict[str, Any]:
    health = _load_health()

    health[
        "circuit_open"
    ] = (
        float(
            health.get(
                "circuit_open_until"
            )
            or 0.0
        )
        > time.time()
    )

    return health
