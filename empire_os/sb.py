"""Compatibility DB facade for EmpireOS.

Legacy callers may continue using empire_os.sb while canonical storage is
migrated. Vendor selection and credentials live behind CanonicalDataGateway.

New business modules should depend on domain repositories/Data Fabric rather
than adding more calls to this compatibility facade.
"""
from __future__ import annotations

from empire_os.canonical_data_gateway import gateway_from_environment


ALIAS = {
    "si_outbox": "outbox_messages",
}


def _table(name: str) -> str:
    return ALIAS.get(name, name)


def _gateway():
    return gateway_from_environment()


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
    if not _configured():
        return []
    return _gateway().select(
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
    if not _configured():
        return []
    return _gateway().insert(
        _table(table),
        row,
        return_repr=return_repr,
    )


def update(
    table: str,
    match: dict,
    values: dict,
) -> list:
    if not _configured():
        return []
    return _gateway().update(
        _table(table),
        match,
        values,
    )


def delete(
    table: str,
    match: dict,
) -> None:
    if not _configured():
        return None
    _gateway().delete(_table(table), match)
    return None


def rpc(
    name: str,
    params: dict | None = None,
) -> object:
    if not _configured():
        return None
    return _gateway().rpc(name, params)
