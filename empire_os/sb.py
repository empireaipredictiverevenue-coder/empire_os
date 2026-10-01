"""Compatibility DB facade for EmpireOS.

Legacy callers may continue using empire_os.sb while canonical storage is
migrated. Vendor selection and credentials live behind CanonicalDataGateway.

New business modules should depend on domain repositories/Data Fabric rather
than adding more calls to this compatibility facade.
"""
from __future__ import annotations

import re
import urllib.parse

from empire_os.data_values import unwrap_data_value
from typing import Any, Mapping

from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.data_query import (
    ConflictAction,
    DataFilter,
    FilterOperator,
    OrderSpec,
)
from empire_os.runtime_env import load_runtime_env
from empire_os.data_query import validate_filter_column


ENV_PATH = "/etc/empire_os.env"

ALIAS = {
    "si_outbox": "outbox_messages",
}

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _table(name: str) -> str:
    return ALIAS.get(name, name)


def _gateway():
    return gateway_from_environment()


def _runtime_gateway():
    return gateway_from_environment(load_runtime_env(ENV_PATH))


def _configured() -> bool:
    """Return whether the selected canonical backend is configured."""
    return _gateway().configured


def select(
    table: str,
    columns: str = "*",
    filters: dict | None = None,
    order: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> list:
    gateway = _gateway()
    if not gateway.configured:
        return []
    return gateway.select(
        _table(table),
        columns,
        filters,
        order,
        limit,
        offset,
    )


def insert(
    table: str,
    row: dict,
    return_repr: bool = True,
) -> list:
    gateway = _gateway()
    if not gateway.configured:
        return []
    return gateway.insert(
        _table(table),
        row,
        return_repr=return_repr,
    )


def update(
    table: str,
    match: dict,
    values: dict,
) -> list:
    gateway = _gateway()
    if not gateway.configured:
        return []
    return gateway.update(
        _table(table),
        match,
        values,
    )


def delete(
    table: str,
    match: dict,
) -> None:
    gateway = _gateway()
    if not gateway.configured:
        return None
    gateway.delete(_table(table), match)
    return None


def rpc(
    name: str,
    params: dict | None = None,
) -> object:
    gateway = _gateway()
    if not gateway.configured:
        return None
    return gateway.rpc(name, params)


def _ident(value: str) -> str:
    if not _IDENT.fullmatch(value):
        raise ValueError(f"unsafe compatibility identifier: {value!r}")
    return value


def _scalar(value: str) -> Any:
    # Query values reaching this function have already been decoded by
    # urllib.parse.parse_qsl() in _table_request_parts().
    #
    # Decoding again with unquote_plus() corrupts legitimate "+" values,
    # notably ISO-8601 timezone offsets such as +00:00.
    text = str(value)

    # PostgREST in.(...) values may be double-quoted, particularly when
    # values contain spaces.  Quotes delimit the value and are not part
    # of the stored scalar.
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].replace(r'\\"', '"').replace(r'\\\\', '\\')

    lowered = text.casefold()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except ValueError:
            pass
    return text


def _data_filter(column: str, expression: str) -> DataFilter:
    column = validate_filter_column(column)
    if expression == "is.null":
        return DataFilter.is_null(column)
    if expression == "not.is.null":
        return DataFilter.is_not_null(column)
    if expression.startswith("not.eq."):
        return DataFilter.ne(column, _scalar(expression[7:]))
    if expression.startswith("not.in.(") and expression.endswith(")"):
        values = expression[8:-1].split(",")
        return DataFilter.not_in(column, tuple(_scalar(v) for v in values))
    if expression.startswith("eq."):
        return DataFilter.eq(column, _scalar(expression[3:]))
    if expression.startswith("gte."):
        return DataFilter.gte(column, _scalar(expression[4:]))
    if expression.startswith("like."):
        pattern = str(_scalar(expression[5:])).replace("*", "%")
        return DataFilter.like(column, pattern)
    if expression.startswith("ilike."):
        pattern = str(_scalar(expression[6:])).replace("*", "%")
        return DataFilter.ilike(column, pattern)
    if expression.startswith("in.(") and expression.endswith(")"):
        values = expression[4:-1].split(",")
        return DataFilter.in_(column, tuple(_scalar(v) for v in values))
    raise ValueError(
        f"unsupported compatibility filter: {column}={expression!r}"
    )


def _order(value: str) -> tuple[OrderSpec, ...]:
    if not value:
        return ()
    result: list[OrderSpec] = []
    for raw in value.split(","):
        parts = [part for part in raw.split(".") if part]
        column = _ident(parts[0])
        descending = "desc" in parts[1:]
        nulls_last = (
            True
            if "nullslast" in parts[1:]
            else False
            if "nullsfirst" in parts[1:]
            else None
        )
        result.append(
            OrderSpec(
                column,
                descending=descending,
                nulls_last=nulls_last,
            )
        )
    return tuple(result)


def _table_request_parts(
    path: str,
) -> tuple[str, str, tuple[DataFilter, ...], tuple[OrderSpec, ...], int, int, tuple[str, ...]]:
    parsed = urllib.parse.urlsplit(path)
    prefix = "/rest/v1/"
    if not parsed.path.startswith(prefix):
        raise ValueError("compatibility request must target /rest/v1/")
    table = _table(_ident(parsed.path[len(prefix):]))
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

    columns = "*"
    limit = 1000
    offset = 0
    order: tuple[OrderSpec, ...] = ()
    filters: list[DataFilter] = []
    conflicts: tuple[str, ...] = ()

    for key, value in pairs:
        if key == "select":
            if "(" in value or ")" in value or ":" in value:
                raise ValueError(
                    "embedded PostgREST selects require a domain repository"
                )
            columns = ",".join(
                _ident(part.strip())
                for part in value.split(",")
                if part.strip()
            ) or "*"
        elif key == "limit":
            limit = max(0, min(int(value), 10000))
        elif key == "offset":
            offset = max(0, int(value))
        elif key == "order":
            order = _order(value)
        elif key == "on_conflict":
            conflicts = tuple(
                _ident(part.strip())
                for part in value.split(",")
                if part.strip()
            )
        else:
            filters.append(_data_filter(key, value))

    return (
        table,
        columns,
        tuple(filters),
        order,
        limit,
        offset,
        conflicts,
    )


def _equality_match(filters: tuple[DataFilter, ...]) -> dict[str, Any]:
    match: dict[str, Any] = {}
    for item in filters:
        if item.operator is not FilterOperator.EQ:
            raise ValueError(
                "compatibility update/delete supports equality filters only"
            )
        match[item.column] = item.value
    if not match:
        raise ValueError(
            "compatibility update/delete requires at least one equality filter"
        )
    return match




def _compat_result(value: Any) -> Any:
    """Normalize native backend values at the legacy transport boundary."""
    return unwrap_data_value(value)


def request_json(
    method: str,
    path: str,
    payload: Any | None = None,
    *,
    prefer: str | None = None,
    allow_egress_probe: bool = False,
) -> Any:
    """Migration-only adapter from old PostgREST-shaped calls to the gateway.

    This function performs no HTTP and holds no vendor credentials. It exists
    only so legacy business modules can remain runnable while specialist waves
    replace their REST-shaped calls with semantic domain repositories.
    """
    if allow_egress_probe:
        raise ValueError(
            "egress recovery probes belong to the selected backend provider"
        )

    gateway = _runtime_gateway()
    if not gateway.configured:
        return None

    # Legacy/PostgREST compatibility boundary:
    # normalize native PostgreSQL/Python values before writes.
    payload = unwrap_data_value(payload)

    verb = str(method or "").strip().upper()
    parsed = urllib.parse.urlsplit(path)
    rpc_prefix = "/rest/v1/rpc/"
    if parsed.path.startswith(rpc_prefix):
        if verb != "POST":
            raise ValueError("canonical RPC compatibility requires POST")
        name = _ident(parsed.path[len(rpc_prefix):])
        params = payload if isinstance(payload, Mapping) else {}
        return unwrap_data_value(
            gateway.rpc(name, dict(params))
        )

    (
        table,
        columns,
        filters,
        ordering,
        limit,
        offset,
        conflicts,
    ) = _table_request_parts(path)

    if verb == "GET":
        return unwrap_data_value(gateway.query(
            table,
            columns,
            filters=filters,
            order=ordering,
            limit=limit,
            offset=offset,
        ))


    if verb == "POST":
        if not isinstance(payload, Mapping):
            raise TypeError(
                "canonical table-write compatibility requires object payload"
            )
        preference = str(prefer or "")
        return_repr = "return=representation" in preference
        if "resolution=merge-duplicates" in preference:
            if not conflicts:
                raise ValueError(
                    "merge-duplicates compatibility requires on_conflict"
                )
            rows = gateway.upsert(
                table,
                dict(payload),
                conflict_columns=conflicts,
                action=ConflictAction.MERGE,
                return_repr=return_repr,
            )
        elif "resolution=ignore-duplicates" in preference:
            rows = gateway.insert_ignore_conflicts(
                table,
                dict(payload),
                conflict_columns=conflicts,
                return_repr=return_repr,
            )
        else:
            rows = gateway.insert(
                table,
                dict(payload),
                return_repr=return_repr,
            )
        return rows if return_repr else None

    if verb == "PATCH":
        if not isinstance(payload, Mapping):
            raise TypeError(
                "canonical table-update compatibility requires object payload"
            )
        return _compat_result(gateway.update(
            table,
            _equality_match(filters),
            dict(payload),
        ))

    if verb == "DELETE":
        gateway.delete(table, _equality_match(filters))
        return None

    raise ValueError(f"unsupported compatibility method: {verb}")
