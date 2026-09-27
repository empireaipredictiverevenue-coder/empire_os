"""Vendor-neutral query and conflict semantics for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class FilterOperator(str, Enum):
    EQ = "eq"
    IN = "in"
    IS_NULL = "is_null"


@dataclass(frozen=True)
class DataFilter:
    column: str
    operator: FilterOperator
    value: Any = None

    @classmethod
    def eq(cls, column: str, value: Any) -> "DataFilter":
        return cls(column, FilterOperator.EQ, value)

    @classmethod
    def in_(cls, column: str, values: Iterable[Any]) -> "DataFilter":
        return cls(column, FilterOperator.IN, tuple(values))

    @classmethod
    def is_null(cls, column: str) -> "DataFilter":
        return cls(column, FilterOperator.IS_NULL, None)


@dataclass(frozen=True)
class OrderSpec:
    column: str
    descending: bool = False


class ConflictAction(str, Enum):
    IGNORE = "ignore"
    MERGE = "merge"
