"""Vendor-neutral query and conflict semantics for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    ILIKE = "ilike"
    GTE = "gte"
    IS_NULL = "is_null"


@dataclass(frozen=True)
class DataFilter:
    column: str
    operator: FilterOperator
    value: Any = None

    def __post_init__(self) -> None:
        if not self.column.strip():
            raise ValueError("filter column is required")
        if self.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            if isinstance(self.value, (str, bytes)) or self.value is None:
                raise ValueError("IN filter requires a value sequence")
            values = tuple(self.value)
            if not values:
                raise ValueError("IN filter requires at least one value")
            object.__setattr__(self, "value", values)
        elif self.operator is FilterOperator.IS_NULL and self.value is not None:
            raise ValueError("IS_NULL filter does not accept a value")

    @classmethod
    def eq(cls, column: str, value: Any) -> "DataFilter":
        return cls(column, FilterOperator.EQ, value)

    @classmethod
    def ne(cls, column: str, value: Any) -> "DataFilter":
        return cls(column, FilterOperator.NE, value)

    @classmethod
    def in_(cls, column: str, values: Iterable[Any]) -> "DataFilter":
        return cls(column, FilterOperator.IN, tuple(values))

    @classmethod
    def not_in(cls, column: str, values: Iterable[Any]) -> "DataFilter":
        return cls(column, FilterOperator.NOT_IN, tuple(values))

    @classmethod
    def ilike(cls, column: str, value: str) -> "DataFilter":
        return cls(column, FilterOperator.ILIKE, value)

    @classmethod
    def gte(cls, column: str, value: Any) -> "DataFilter":
        return cls(column, FilterOperator.GTE, value)

    @classmethod
    def is_null(cls, column: str) -> "DataFilter":
        return cls(column, FilterOperator.IS_NULL, None)


@dataclass(frozen=True)
class OrderSpec:
    column: str
    descending: bool = False
    nulls_last: bool | None = None

    def __post_init__(self) -> None:
        if not self.column.strip():
            raise ValueError("order column is required")


class ConflictAction(str, Enum):
    IGNORE = "ignore"
    MERGE = "merge"
