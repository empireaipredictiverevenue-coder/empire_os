"""Governed Predictive Cloud V3 forecast registry contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.predictive_cloud_v3 import DirectionalForecast, MIN_FORECAST_SAMPLES


@dataclass(frozen=True)
class ForecastRegistryRecord:
    forecast_key: str
    model_name: str
    model_version: str
    dimension_key: str
    forecast: DirectionalForecast
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        for name, value in (
            ("forecast_key", self.forecast_key),
            ("model_name", self.model_name),
            ("model_version", self.model_version),
            ("dimension_key", self.dimension_key),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        if not self.forecast.available:
            raise ValueError("only available forecasts may be registered")
        if self.forecast.sample_count < MIN_FORECAST_SAMPLES:
            raise ValueError("forecast evidence gate not satisfied")
        if self.forecast.direction not in {"up", "down", "flat"}:
            raise ValueError("registered forecast direction must be bounded")
        if self.forecast.predicted_value is None:
            raise ValueError("predicted_value required")
        if self.forecast.r_squared is None:
            raise ValueError("r_squared required")
        if self.forecast.evidence_confidence is None:
            raise ValueError("evidence_confidence required")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")
