"""Health/status view for Search Intelligence."""
from __future__ import annotations

from .config import SearchIntelligenceConfig


def search_health(config: SearchIntelligenceConfig | None = None) -> dict:
    cfg = config or SearchIntelligenceConfig.from_env()
    return {
        "ok": True,
        "module": "empire-search-intelligence",
        "execution_mode": cfg.mode.value,
        "mutations_enabled": False,
        "quality_threshold": cfg.quality_threshold,
        "search_console": {
            "enabled": False,
            "status": "credentials_not_configured",
        },
        "serp_source": {
            "status": "available_via_search_fabric",
            "writes_enabled": False,
        },
        "repository": {
            "status": "migration_prepared_not_activated",
            "canonical_database": "supabase",
        },
    }
