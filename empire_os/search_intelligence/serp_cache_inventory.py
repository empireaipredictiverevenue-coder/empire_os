"""Bounded read-only inventory of the EXISTING Search Fabric cache.

Counts provenance-checked local source envelopes, not live Google ranks.
Never emits queries, search-result URLs, snippets, titles or customer data.
Never calls any engine, endpoint, API, database, writer or paid provider.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = "empire.search_intelligence.serp_cache_inventory.v1"
DEFAULT_CACHE = Path("/srv/empire_os/runtime/search/cache")
ALLOWED_ENGINES = frozenset({
    "bing_html", "bing_rss", "duckduckgo_html", "duckduckgo_lite",
    "brave_web", "mojeek",
})
FILE_RE = re.compile(r"^([a-z][a-z0-9_]{1,40})_([0-9a-f]{16})\.json$")
TTL_SECONDS = 86400
FILE_LIMIT = 2500
MAX_FILE_BYTES = 65536
TOTAL_BYTES_LIMIT = 32 * 1024 * 1024


class SerpCacheInventoryHeld(ValueError):
    """Return no misleading readiness when source boundaries are unknown."""


def inspect_cache(cache_dir: Path = DEFAULT_CACHE, *, now: float | None = None) -> dict:
    if (cache_dir.is_symlink() or not cache_dir.is_dir()):
        raise SerpCacheInventoryHeld("SEARCH_FABRIC_CACHE_ROOT_UNAVAILABLE")
    timestamp = datetime.now(timezone.utc).timestamp() if now is None else now
    if (type(timestamp) not in (float,int) or not math.isfinite(timestamp)
            or timestamp < 0):
        raise SerpCacheInventoryHeld("INVALID_OBSERVATION_CLOCK")
    files = sorted(cache_dir.iterdir(), key=lambda f: f.name)
    if len(files) > FILE_LIMIT:
        raise SerpCacheInventoryHeld("SEARCH_FABRIC_CACHE_FILE_LIMIT_EXCEEDED")
    total_bytes = 0
    readable = 0
    invalid = 0
    fresh = 0
    stale = 0
    engines = Counter()
    for path in files:
        if path.is_symlink() or not path.is_file():
            invalid += 1
            continue
        match = FILE_RE.fullmatch(path.name)
        if not match or match.group(1) not in ALLOWED_ENGINES:
            invalid += 1
            continue
        stat = path.stat()
        if stat.st_size > MAX_FILE_BYTES or stat.st_size < 2:
            invalid += 1
            continue
        total_bytes += stat.st_size
        if total_bytes > TOTAL_BYTES_LIMIT:
            raise SerpCacheInventoryHeld("SEARCH_FABRIC_CACHE_BYTES_LIMIT_EXCEEDED")
        try:
            record = json.loads(path.read_text("utf8"))
            if not isinstance(record, dict):
                raise ValueError("not a cache envelope")
            ts = record.get("ts")
            if type(ts) not in (int,float) or not math.isfinite(ts):
                raise ValueError("bad timestamp")
            data = record.get("data")
            if not isinstance(data, dict):
                raise ValueError("missing cached search data")
            params = data.get("searchParameters")
            if not isinstance(params, dict):
                raise ValueError("missing searchParameters")
            engine, digest = match.groups()
            query = params.get("q")
            num = params.get("num")
            if (params.get("engine") != engine or not isinstance(query,str)
                    or not 1 <= len(query.strip()) <= 256
                    or type(num) is not int or not 1 <= num <= 20
                    or hashlib.sha256(f"{engine}:{query}:{num}".encode()).hexdigest()[:16] != digest):
                raise ValueError("search cache key mismatch")
            organic = data.get("organic")
            if not isinstance(organic, list) or not organic or len(organic) > num:
                raise ValueError("missing organic rows")
            if params.get("quality_gate") not in ("lexical_v1","lexical_v2"):
                raise ValueError("unrecognized lexical gate")
            for row in organic:
                if (not isinstance(row,dict) or type(row.get("position")) is not int
                        or not 1 <= row["position"] <= 20
                        or not isinstance(row.get("title"),str) or not row["title"]
                        or not isinstance(row.get("link"),str)
                        or not row["link"].startswith(("https://","http://"))):
                    raise ValueError("untrusted organic row")
            age = timestamp - ts
            readable += 1
            # Freshness is source-record age, not a verified observation by Google.
            if 0 <= age < TTL_SECONDS:
                fresh += 1
                engines[engine] += 1
            else:
                stale += 1
        except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
            invalid += 1
    if invalid + readable != len(files) or stale + fresh != readable:
        raise SerpCacheInventoryHeld("SEARCH_FABRIC_CACHE_AGGREGATE_INCONSISTENT")
    return {
        "schema_version": SCHEMA,
        "status": "CACHE_INVENTORY_OBSERVED",
        "source": "existing_search_fabric_local_cache",
        "mode": "READ_ONLY",
        "ttl_hours": 24,
        "cache_files_seen": len(files),
        "cache_envelopes_valid": readable,
        "cache_envelopes_invalid": invalid,
        "cache_fresh_candidate_count": fresh,
        "cache_stale_candidate_count": stale,
        "cache_fresh_candidates_by_engine": dict(sorted(engines.items())),
        "live_serp_engine_probed": False,
        "external_search_queries_sent": False,
        "paid_api_calls": 0,
        "independent_google_rank_positions_verified": False,
        "cached_engine_positions_are_google_ranks": False,
        "target_buyer_queries_verified": False,
        "customer_records_accessed": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }
