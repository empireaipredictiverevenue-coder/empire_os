"""Explicit typed values crossing the Empire Data Fabric boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class JsonValue:
    """Mark a value as PostgreSQL jsonb instead of an SQL array/scalar."""

    value: Any


def json_value(value: Any) -> JsonValue:
    return JsonValue(value)


def unwrap_data_value(value: Any) -> Any:
    """Return JSON-serializable plain values for HTTP/legacy transports."""

    if isinstance(value, JsonValue):
        return unwrap_data_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): unwrap_data_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [unwrap_data_value(item) for item in value]
    if isinstance(value, list):
        return [unwrap_data_value(item) for item in value]
    return value
