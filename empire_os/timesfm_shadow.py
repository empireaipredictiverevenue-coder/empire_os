"""Optional TimesFM 2.5 shadow-forecast adapter.

TimesFM is a model backend, never a source of observed truth. The default
EmpireOS path stays disabled/fail-closed unless explicitly configured.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from typing import Any, Protocol, Sequence


TIMESFM_25_MODEL_ID = "google/timesfm-2.5-200m-pytorch"


@dataclass(frozen=True)
class TimesFmShadowForecast:
    available: bool
    metric: str
    horizon_steps: int
    context_samples: int
    model_id: str
    point_forecast: tuple[float, ...]
    quantile_forecast: tuple[tuple[float, ...], ...] = ()
    reason: str | None = None
    source: str = "modeled_forecast"
    execution_authority: str = "none"
    creates_actuals: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimesFmProvider(Protocol):
    def status(self) -> dict[str, Any]:
        ...

    def forecast(
        self,
        *,
        metric: str,
        values: Sequence[float],
        horizon_steps: int,
    ) -> TimesFmShadowForecast:
        ...


class DisabledTimesFmProvider:
    def __init__(self, reason: str = "timesfm_shadow_disabled") -> None:
        self.reason = reason

    def status(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "available": False,
            "reason": self.reason,
            "model_id": TIMESFM_25_MODEL_ID,
            "mode": "SHADOW",
            "execution_authority": "none",
        }

    def forecast(
        self,
        *,
        metric: str,
        values: Sequence[float],
        horizon_steps: int,
    ) -> TimesFmShadowForecast:
        return TimesFmShadowForecast(
            available=False,
            metric=str(metric),
            horizon_steps=int(horizon_steps),
            context_samples=len(tuple(values)),
            model_id=TIMESFM_25_MODEL_ID,
            point_forecast=(),
            reason=self.reason,
        )


class TimesFm25LocalProvider:
    """Lazy local CPU/GPU adapter for the Apache-2.0 TimesFM 2.5 weights."""

    def __init__(
        self,
        *,
        model_id: str = TIMESFM_25_MODEL_ID,
        max_context: int = 1024,
        max_horizon: int = 256,
        cache_dir: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.max_context = max(64, min(int(max_context), 16_384))
        self.max_horizon = max(1, min(int(max_horizon), 1000))
        self.cache_dir = cache_dir
        self._model = None

    def status(self) -> dict[str, Any]:
        package_available = importlib.util.find_spec("timesfm") is not None
        return {
            "enabled": True,
            "available": package_available,
            "package_available": package_available,
            "model_loaded": self._model is not None,
            "reason": None if package_available else "timesfm_package_unavailable",
            "model_id": self.model_id,
            "mode": "SHADOW",
            "execution_authority": "none",
        }

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            import timesfm
        except ImportError as exc:
            raise RuntimeError("timesfm_package_unavailable") from exc

        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            self.model_id,
            cache_dir=self.cache_dir,
            force_download=False,
        )
        model.compile(
            timesfm.ForecastConfig(
                max_context=self.max_context,
                max_horizon=self.max_horizon,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
            )
        )
        self._model = model
        return model

    def forecast(
        self,
        *,
        metric: str,
        values: Sequence[float],
        horizon_steps: int,
    ) -> TimesFmShadowForecast:
        metric_name = str(metric or "").strip()
        if not metric_name:
            raise ValueError("metric required")
        horizon = int(horizon_steps)
        if horizon < 1 or horizon > self.max_horizon:
            raise ValueError("horizon_steps out of bounds")
        raw = tuple(float(value) for value in values)
        if len(raw) < 7:
            return TimesFmShadowForecast(
                available=False,
                metric=metric_name,
                horizon_steps=horizon,
                context_samples=len(raw),
                model_id=self.model_id,
                point_forecast=(),
                reason="minimum_7_observations_required",
            )
        if any(value < 0 for value in raw):
            raise ValueError("observed values must be nonnegative")

        try:
            import numpy as np
            model = self._load()
            point, quantiles = model.forecast(
                horizon=horizon,
                inputs=[np.asarray(raw, dtype=np.float32)],
            )
        except Exception as exc:
            return TimesFmShadowForecast(
                available=False,
                metric=metric_name,
                horizon_steps=horizon,
                context_samples=len(raw),
                model_id=self.model_id,
                point_forecast=(),
                reason=f"timesfm_forecast_failed:{type(exc).__name__}",
            )

        point_row = tuple(
            max(0.0, float(value))
            for value in point[0][:horizon]
        )
        quantile_rows: tuple[tuple[float, ...], ...] = ()
        if quantiles is not None:
            quantile_rows = tuple(
                tuple(max(0.0, float(v)) for v in step)
                for step in quantiles[0][:horizon]
            )
        return TimesFmShadowForecast(
            available=True,
            metric=metric_name,
            horizon_steps=horizon,
            context_samples=len(raw),
            model_id=self.model_id,
            point_forecast=point_row,
            quantile_forecast=quantile_rows,
        )


def configured_timesfm_provider() -> TimesFmProvider:
    enabled = str(
        os.getenv("EMPIRE_TIMESFM_SHADOW_ENABLED", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return DisabledTimesFmProvider()

    approved = str(
        os.getenv("EMPIRE_TIMESFM_SHADOW_APPROVED", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not approved:
        return DisabledTimesFmProvider("timesfm_shadow_not_approved")

    return TimesFm25LocalProvider(
        model_id=os.getenv(
            "EMPIRE_TIMESFM_MODEL_ID",
            TIMESFM_25_MODEL_ID,
        ).strip() or TIMESFM_25_MODEL_ID,
        max_context=int(os.getenv("EMPIRE_TIMESFM_MAX_CONTEXT", "1024")),
        max_horizon=int(os.getenv("EMPIRE_TIMESFM_MAX_HORIZON", "256")),
        cache_dir=os.getenv("EMPIRE_TIMESFM_CACHE_DIR") or None,
    )
