"""Vendor-neutral query and conflict semantics for Empire Data Cloud."""
from __future__ import annotations

import re

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable



_FILTER_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)

_FILTER_JSON_PATH_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*"
    r"(?:(?:->>|->)[A-Za-z_][A-Za-z0-9_]*)+$"
)

_FILTER_JSON_PATH_TOKEN_RE = re.compile(
    r"(->>|->)([A-Za-z_][A-Za-z0-9_]*)"
)


def validate_filter_column(column: str) -> str:
    """Validate a neutral scalar or PostgREST JSON filter expression."""

    value = str(column).strip()

    if _FILTER_IDENTIFIER_RE.fullmatch(value):
        return value

    if _FILTER_JSON_PATH_RE.fullmatch(value):
        return value

    raise ValueError(
        f"unsafe filter column expression: {column!r}"
    )


def postgres_filter_column(column: str) -> str:
    """Compile a validated neutral filter column to safe PostgreSQL SQL."""

    value = validate_filter_column(column)

    if "->" not in value:
        return f'"{value}"'

    base_match = re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*",
        value,
    )

    if base_match is None:
        raise ValueError(
            f"invalid JSON filter column: {column!r}"
        )

    base = base_match.group(0)
    tail = value[len(base):]

    tokens = _FILTER_JSON_PATH_TOKEN_RE.findall(tail)

    if not tokens:
        raise ValueError(
            f"invalid JSON filter path: {column!r}"
        )

    return f'"{base}"' + "".join(
        f"{operator}'{key}'"
        for operator, key in tokens
    )


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"
    GTE = "gte"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


@dataclass(frozen=True)
class DataFilter:
    column: str
    operator: FilterOperator
    value: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "column",
            validate_filter_column(self.column),
        )
        if self.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            if isinstance(self.value, (str, bytes)) or self.value is None:
                raise ValueError("IN filter requires a value sequence")
            values = tuple(self.value)
            if not values:
                raise ValueError("IN filter requires at least one value")
            object.__setattr__(self, "value", values)
        elif self.operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL) and self.value is not None:
            raise ValueError(f"{self.operator.value.upper()} filter does not accept a value")

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
    def like(cls, column: str, value: str) -> "DataFilter":
        return cls(column, FilterOperator.LIKE, value)
    @classmethod
    def ilike(cls, column: str, value: str) -> "DataFilter":
        return cls(column, FilterOperator.ILIKE, value)

    @classmethod
    def gte(cls, column: str, value: Any) -> "DataFilter":
        return cls(column, FilterOperator.GTE, value)

    @classmethod
    def is_null(cls, column: str) -> "DataFilter":
        return cls(column, FilterOperator.IS_NULL, None)

    @classmethod
    def is_not_null(cls, column: str) -> "DataFilter":
        return cls(column, FilterOperator.IS_NOT_NULL, None)


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
