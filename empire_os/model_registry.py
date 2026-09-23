"""Empire OS model registry.

Combines controlled Empire policy metadata with live provider discovery.

The registry:
- contains no API secrets
- preserves explicit Empire policy entries
- imports live OpenCode Zen catalogue entries when available
- treats discovered pricing/performance as unknown until verified/calibrated
- never claims provider availability implies model superiority
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = "/srv/empire_os/config/model_registry.json"
DEFAULT_ZEN_CACHE = "/srv/empire_os/runtime/llm/opencode_zen_models.json"


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    provider: str
    model: str
    capabilities: frozenset[str] = frozenset()
    reasoning: bool = False
    vision: bool = False

    # These are priors until Empire calibration data replaces them.
    quality: dict[str, float] = field(default_factory=dict)

    # USD per 1k tokens.
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None

    free: bool = False
    enabled: bool = True
    priority: int = 100

    # True only when pricing has actually been verified.
    pricing_known: bool = False

    # Runtime availability/health metadata.
    available: bool = True
    health: str = "unknown"

    # Media/licensing metadata. Unknown values fail closed for commercial
    # asset generation; "open weights" does not imply commercial permission.
    license_id: str | None = None
    commercial_permission: bool | None = None
    attribution_required: bool | None = None
    deployment: str = "unknown"
    vram_gb: float | None = None
    latency_ms: float | None = None
    last_benchmark: str | None = None
    last_reviewed: str | None = None
    media_tasks: frozenset[str] = frozenset()

    metadata: dict[str, Any] = field(default_factory=dict)

    def quality_for(self, task: str) -> float:
        return max(
            0.0,
            min(
                1.0,
                float(
                    self.quality.get(
                        task.lower(),
                        self.quality.get("default", 0.5),
                    )
                ),
            ),
        )

    @property
    def cost_known(self) -> bool:
        return (
            self.pricing_known
            and self.cost_per_1k_input is not None
            and self.cost_per_1k_output is not None
        )

    def commercial_media_eligible(self, task: str) -> bool:
        requested = str(task or "").strip().lower()
        return (
            bool(requested)
            and self.enabled
            and self.available
            and self.commercial_permission is True
            and bool(self.license_id)
            and (
                requested in self.media_tasks
                or requested in self.capabilities
            )
        )


class ModelRegistry:
    """Merged policy + provider-discovery model registry."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.environ.get(
            "EMPIRE_MODEL_REGISTRY",
            DEFAULT_REGISTRY,
        ))
        self.zen_cache = Path(os.environ.get(
            "EMPIRE_ZEN_CATALOG_CACHE",
            DEFAULT_ZEN_CACHE,
        ))
        self._models = self._load()

    def _load(self) -> dict[str, ModelSpec]:
        configured = self._load_file_registry()
        if not configured:
            configured = self._built_in()

        # Live provider discovery augments, but never silently overwrites,
        # explicit Empire policy entries.
        discovered = self._load_zen_catalog()

        for spec in discovered:
            configured.setdefault(spec.model_id, spec)

        return configured

    def _load_file_registry(self) -> dict[str, ModelSpec]:
        if not self.path.exists():
            return {}

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        models: dict[str, ModelSpec] = {}

        for item in raw.get("models", []):
            try:
                spec = ModelSpec(
                    model_id=str(item["model_id"]),
                    provider=str(item["provider"]),
                    model=str(item["model"]),
                    capabilities=frozenset(item.get("capabilities", [])),
                    reasoning=bool(item.get("reasoning", False)),
                    vision=bool(item.get("vision", False)),
                    quality={
                        str(k): float(v)
                        for k, v in item.get("quality", {}).items()
                    },
                    cost_per_1k_input=(
                        float(item["cost_per_1k_input"])
                        if item.get("cost_per_1k_input") is not None
                        else None
                    ),
                    cost_per_1k_output=(
                        float(item["cost_per_1k_output"])
                        if item.get("cost_per_1k_output") is not None
                        else None
                    ),
                    free=bool(item.get("free", False)),
                    enabled=bool(item.get("enabled", True)),
                    priority=int(item.get("priority", 100)),
                    pricing_known=bool(item.get("pricing_known", False)),
                    available=bool(item.get("available", True)),
                    health=str(item.get("health", "unknown")),
                    license_id=(
                        str(item.get("license_id")).strip()
                        if item.get("license_id")
                        else None
                    ),
                    commercial_permission=(
                        bool(item["commercial_permission"])
                        if item.get("commercial_permission") is not None
                        else None
                    ),
                    attribution_required=(
                        bool(item["attribution_required"])
                        if item.get("attribution_required") is not None
                        else None
                    ),
                    deployment=str(
                        item.get("deployment") or "unknown"
                    ),
                    vram_gb=(
                        float(item["vram_gb"])
                        if item.get("vram_gb") is not None
                        else None
                    ),
                    latency_ms=(
                        float(item["latency_ms"])
                        if item.get("latency_ms") is not None
                        else None
                    ),
                    last_benchmark=(
                        str(item.get("last_benchmark"))
                        if item.get("last_benchmark")
                        else None
                    ),
                    last_reviewed=(
                        str(item.get("last_reviewed"))
                        if item.get("last_reviewed")
                        else None
                    ),
                    media_tasks=frozenset(
                        str(value).strip().lower()
                        for value in (item.get("media_tasks") or [])
                        if str(value).strip()
                    ),
                    metadata=dict(item.get("metadata", {})),
                )
                models[spec.model_id] = spec
            except (KeyError, TypeError, ValueError):
                continue

        return models

    def _load_zen_catalog(self) -> list[ModelSpec]:
        if not self.zen_cache.exists():
            return []

        try:
            raw = json.loads(self.zen_cache.read_text(encoding="utf-8"))
        except Exception:
            return []

        result: list[ModelSpec] = []

        for item in raw.get("models", []):
            model = str(item.get("model") or "").strip()
            if not model:
                continue

            model_id = str(
                item.get("model_id") or f"zen:{model}"
            )

            # Discovery proves availability, not quality.
            result.append(
                ModelSpec(
                    model_id=model_id,
                    provider="opencode",
                    model=model,
                    capabilities=frozenset(
                        item.get("capabilities") or ["general"]
                    ),
                    reasoning=bool(item.get("reasoning", False)),
                    vision=False,
                    quality={
                        "default": 0.50,
                    },
                    cost_per_1k_input=None,
                    cost_per_1k_output=None,
                    free=bool(item.get("free", False)),
                    enabled=True,
                    priority=40 if item.get("free") else 50,
                    pricing_known=False,
                    available=bool(item.get("available", True)),
                    health="discovered",
                    metadata={
                        "discovered": True,
                        "catalog_source": "opencode_zen",
                        "pricing_status": "unknown",
                        "quality_status": "uncalibrated",
                        "discovery_record": item,
                    },
                )
            )

        return result

    def _built_in(self) -> dict[str, ModelSpec]:
        return {
            "ollama-local-fallback": ModelSpec(
                model_id="ollama-local-fallback",
                provider="ollama",
                model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
                capabilities=frozenset({
                    "general",
                    "classification",
                    "extraction",
                    "summarization",
                    "coding",
                }),
                reasoning=False,
                quality={
                    "default": 0.45,
                    "coding": 0.50,
                },
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
                free=True,
                priority=10,
                pricing_known=True,
                health="unknown",
                metadata={"local_fallback": True},
            )
        }

    def all(self) -> list[ModelSpec]:
        return [
            m for m in self._models.values()
            if m.enabled and m.available
        ]

    def get(self, model_id: str) -> ModelSpec | None:
        return self._models.get(model_id)

    def providers(self) -> list[str]:
        return sorted({m.provider for m in self.all()})

    def candidates(
        self,
        *,
        task: str,
        required_capabilities: set[str] | None = None,
        require_reasoning: bool = False,
        require_vision: bool = False,
    ) -> list[ModelSpec]:
        required_capabilities = required_capabilities or set()
        out: list[ModelSpec] = []

        for model in self.all():
            if require_reasoning and not model.reasoning:
                continue
            if require_vision and not model.vision:
                continue
            if (
                required_capabilities
                and not required_capabilities.issubset(model.capabilities)
            ):
                continue
            out.append(model)

        out.sort(
            key=lambda m: (
                m.quality_for(task),
                1 if m.pricing_known else 0,
                -m.priority,
            ),
            reverse=True,
        )

        return out

    def summary(self) -> dict[str, Any]:
        models = self.all()

        return {
            "total": len(models),
            "providers": self.providers(),
            "reasoning": sum(1 for m in models if m.reasoning),
            "free": sum(1 for m in models if m.free),
            "pricing_known": sum(1 for m in models if m.pricing_known),
            "discovered": sum(
                1 for m in models
                if m.metadata.get("discovered")
            ),
            "commercial_media_permission_verified": sum(
                1 for m in models
                if m.commercial_permission is True and m.license_id
            ),
            "commercial_media_permission_unknown": sum(
                1 for m in models
                if m.commercial_permission is None
            ),
        }

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "model": m.model,
                "capabilities": sorted(m.capabilities),
                "reasoning": m.reasoning,
                "vision": m.vision,
                "quality": m.quality,
                "cost_per_1k_input": m.cost_per_1k_input,
                "cost_per_1k_output": m.cost_per_1k_output,
                "free": m.free,
                "enabled": m.enabled,
                "priority": m.priority,
                "pricing_known": m.pricing_known,
                "available": m.available,
                "health": m.health,
                "license_id": m.license_id,
                "commercial_permission": m.commercial_permission,
                "attribution_required": m.attribution_required,
                "deployment": m.deployment,
                "vram_gb": m.vram_gb,
                "latency_ms": m.latency_ms,
                "last_benchmark": m.last_benchmark,
                "last_reviewed": m.last_reviewed,
                "media_tasks": sorted(m.media_tasks),
                "discovered": bool(m.metadata.get("discovered")),
            }
            for m in self.all()
        ]
