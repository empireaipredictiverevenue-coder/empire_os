"""Health/status view for Search Intelligence."""
from __future__ import annotations

from .config import SearchIntelligenceConfig
from .search_console import SearchConsoleStatus, search_console_status_from_env


def search_health(
    config: SearchIntelligenceConfig | None = None,
    *,
    search_console_status: SearchConsoleStatus | None = None,
) -> dict:
    cfg = config or SearchIntelligenceConfig.from_env()
    # The local API's Search Console adapter is already separately
    # governed. Never report a hard-coded false when the running adapter
    # has a verified, configured status.
    console = (
        search_console_status
        if search_console_status is not None
        else search_console_status_from_env()
    )
    return {
        "ok": True,
        "module": "empire-search-intelligence",
        "execution_mode": cfg.mode.value,
        "mutations_enabled": False,
        "quality_threshold": cfg.quality_threshold,
        "search_console": {
            **console.as_dict(),
            "status": console.reason,
        },
        "serp_source": {
            # The Search Fabric integration exists; this status endpoint does
            # NOT execute a search, read an organic result or verify a rank.
            # Do not mistake integration readiness for witnessed demand.
            "status": "INTEGRATION_PRESENT_OBSERVATION_UNVERIFIED",
            "integration": "search_fabric",
            "verified_organic_observations": None,
            "last_verified_organic_observation_at": None,
            "rank_positions_attested": False,
            "query_demand_observed": None,
            "writes_enabled": False,
        },
        "repository": {
            "status": "canonical_repository_runtime_gated",
            "canonical_database": "empiredb",
        },
    }
