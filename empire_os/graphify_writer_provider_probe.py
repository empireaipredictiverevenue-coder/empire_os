"""Bounded, read-only local writer-route readiness using existing Empire Coder code.

Does not invoke inference, mint patches, schedule tasks, read prompt bodies,
change provider health, configure paid remote models or expose credentials.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from empire_os.coder.ollama_provider import OllamaProvider
from empire_os.coder.orchestrator import (
    LOCAL_WRITER_MODEL, local_ollama_profiles,
)
from empire_os.coder.provider_health import ProviderHealth
from empire_os.coder.router import ModelRouter

SCHEMA = "empire.graphify.local_writer_provider_probe.v1"
# A fixed software-routing complexity example, not task or customer data.
_ROUTING_EXAMPLE = "Refactor an existing production architecture module"


def probe_current_writer_provider(repo_root: Path) -> dict[str, Any]:
    """Check actual local server, installed model inventory and cooldown."""
    root = Path(repo_root).resolve(strict=True)
    base = {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "authority": "none",
        "status": "CURRENT_WRITER_ROUTE_UNVERIFIED",
        "local_ollama_endpoint_responding": False,
        "installed_local_model_count": None,
        "local_writer_profile_count": 0,
        "preferred_writer_model_installed": False,
        "active_writer_route_eligible": False,
        "medium_writer_route_eligible": False,
        "preferred_writer_cooldown_active": False,
        "route_provider": None,
        "route_local": None,
        "model_inference_performed": False,
        "patch_or_task_created": False,
        "credentials_exported": False,
        "production_model_config_modified": False,
    }
    try:
        provider = OllamaProvider(timeout_seconds=5)
        if not provider.health():
            base["status"] = "CURRENT_LOCAL_OLLAMA_NOT_RESPONDING"
            return base
        base["local_ollama_endpoint_responding"] = True
        names = provider.models()
        base["installed_local_model_count"] = len(names)
        base["preferred_writer_model_installed"] = LOCAL_WRITER_MODEL in names
        profiles = local_ollama_profiles(names)
        writers = tuple(profile for profile in profiles if "writer" in profile.roles)
        base["local_writer_profile_count"] = len(writers)
        cooldown = ProviderHealth(
            root / "runtime/coder/model_health.json"
        ).excluded_routes()
        router = ModelRouter(profiles)
        base["preferred_writer_cooldown_active"] = (
            ("ollama", LOCAL_WRITER_MODEL) in cooldown
        )
        medium = router.route(
            "Implement an existing module feature", role="writer",
            exclude=cooldown,
        )
        base["medium_writer_route_eligible"] = (
            medium.provider == "ollama" and medium.local
        )
        route = router.route(
            _ROUTING_EXAMPLE, role="writer", exclude=cooldown,
        )
        if route.provider == "ollama" and route.local:
            base.update({
                "status": "CURRENT_LOCAL_WRITER_ROUTE_CONFIGURED",
                "active_writer_route_eligible": True,
                "route_provider": "ollama",
                "route_local": True,
            })
        else:
            base["status"] = (
                "COMPLEX_WRITER_IN_ACTIVE_COOLDOWN"
                if base["preferred_writer_cooldown_active"]
                else "COMPLEX_WRITER_MODEL_MISSING_OR_UNAVAILABLE"
            )
        return base
    except (OSError, ValueError, TypeError, TimeoutError):
        base["status"] = "CURRENT_WRITER_ROUTE_CHECK_FAILED"
        return base
