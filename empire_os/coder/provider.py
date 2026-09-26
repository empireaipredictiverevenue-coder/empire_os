"""Model-provider abstraction for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .context import ContextPack
from .models import ModelRoute


@dataclass(frozen=True)
class ModelRequest:
    task_id: str
    instruction: str
    context: ContextPack
    route: ModelRoute
    max_output_chars: int = 6_000


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    text: str
    usage: dict[str, int] | None = None
    error: str | None = None
    actionable: bool = False


class ModelProvider(Protocol):
    name: str

    def complete(self, request: ModelRequest) -> ModelResponse:
        ...


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> ModelProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"model provider not configured: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


class DisabledProvider:
    """Fail-closed placeholder when inference is not configured."""
    name = "unconfigured"

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            provider=self.name,
            model="none",
            text="",
            error="model_provider_not_configured",
        )
