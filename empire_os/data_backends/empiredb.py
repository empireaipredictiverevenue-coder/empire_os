"""EmpireDB PostgreSQL provider for CanonicalDataGateway.

Internal compatibility provider only. It exposes bounded table CRUD with
identifier validation and parameterized values. Arbitrary SQL and generic RPC
execution are intentionally unsupported.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.postgres import PostgresConnector
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import ConflictAction, DataFilter, FilterOperator, OrderSpec


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(value: str) -> str:
    if not _IDENT.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


def _columns(value: str) -> str:
    if value == "*":
        return "*"
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("at least one column is required")
    return ", ".join(_ident(part) for part in parts)


def _order_clause(value: str | None) -> str:
    if not value:
        return ""
    parts = value.split(".")
    if len(parts) == 1:
        column, direction = parts[0], "ASC"
    elif len(parts) == 2:
        column, raw_direction = parts
        direction = raw_direction.upper()
    else:
        raise ValueError("unsupported order expression")
    if direction not in {"ASC", "DESC"}:
        raise ValueError("order direction must be asc or desc")
    return f" ORDER BY {_ident(column)} {direction}"


def _rows(cursor: Any) -> list[dict[str, Any]]:
    if cursor.description is None:
        return []
    names = [
        item.name if hasattr(item, "name") else item[0]
        for item in cursor.description
    ]
    return [
        dict(zip(names, row, strict=True))
        for row in cursor.fetchall()
    ]


class EmpireDbProvider:
    backend = DataBackend.EMPIREDB

    def __init__(self, connector: PostgresConnector) -> None:
        self._connector = connector

    def configured(self) -> bool:
        return bool(self._connector.config_snapshot.get("dsn_configured"))

    def _connection(self):
        return self._connector._open_connection()

    def _adapt(self, value: Any) -> Any:
        return self._connector.adapt_value(value)

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Mapping[str, object] | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        limit = max(0, min(int(limit), 10000))
        offset = max(0, int(offset))
        params: list[object] = []
        where_parts: list[str] = []

        for key, value in (filters or {}).items():
            where_parts.append(f"{_ident(str(key))} = %s")
            params.append(value)

        sql = f"SELECT {_columns(columns)} FROM public.{_ident(table)}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += _order_clause(order)
        sql += " LIMIT %s OFFSET %s"
        params.extend((limit, offset))

        connection = self._connection()
        try:
            return _rows(connection.execute(sql, tuple(params)))
        finally:
            connection.close()

    def query(
        self,
        table: str,
        columns: str = "*",
        *,
        filters: Sequence[DataFilter] = (),
        order: Sequence[OrderSpec] = (),
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        limit = max(0, min(int(limit), 10000))
        offset = max(0, int(offset))
        params: list[object] = []
        where_parts: list[str] = []

        for item in filters:
            column = _ident(item.column)
            if item.operator is FilterOperator.EQ:
                where_parts.append(f"{column} = %s")
                params.append(item.value)
            elif item.operator is FilterOperator.NE:
                where_parts.append(f"{column} <> %s")
                params.append(item.value)
            elif item.operator is FilterOperator.ILIKE:
                where_parts.append(f"{column} ILIKE %s")
                params.append(item.value)
            elif item.operator is FilterOperator.GTE:
                where_parts.append(f"{column} >= %s")
                params.append(item.value)
            elif item.operator is FilterOperator.IS_NULL:
                where_parts.append(f"{column} IS NULL")
            elif item.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
                values = tuple(item.value or ())
                if not values:
                    return []
                placeholders = ", ".join("%s" for _ in values)
                keyword = "IN" if item.operator is FilterOperator.IN else "NOT IN"
                where_parts.append(f"{column} {keyword} ({placeholders})")
                params.extend(values)
            else:
                raise ValueError(f"unsupported filter operator: {item.operator}")

        sql = f"SELECT {_columns(columns)} FROM public.{_ident(table)}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if order:
            sql += " ORDER BY " + ", ".join(
                (
                    f"{_ident(item.column)} "
                    f"{'DESC' if item.descending else 'ASC'}"
                    + (
                        " NULLS LAST"
                        if item.nulls_last is True
                        else " NULLS FIRST"
                        if item.nulls_last is False
                        else ""
                    )
                )
                for item in order
            )
        sql += " LIMIT %s OFFSET %s"
        params.extend((limit, offset))

        connection = self._connection()
        try:
            return _rows(connection.execute(sql, tuple(params)))
        finally:
            connection.close()

    def count(
        self,
        table: str,
        filters: Mapping[str, object] | None = None,
    ) -> int:
        params: list[object] = []
        where_parts: list[str] = []
        for key, value in (filters or {}).items():
            where_parts.append(f"{_ident(str(key))} = %s")
            params.append(value)

        sql = f"SELECT count(*) AS count FROM public.{_ident(table)}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        connection = self._connection()
        try:
            cursor = connection.execute(sql, tuple(params))
            rows = _rows(cursor)
            if len(rows) != 1 or "count" not in rows[0]:
                raise RuntimeError("EmpireDB count returned invalid shape")
            return int(rows[0]["count"])
        finally:
            connection.close()

    def insert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        if not row:
            raise ValueError("insert row cannot be empty")
        names = [str(name) for name in row]
        sql = (
            f"INSERT INTO public.{_ident(table)} "
            f"({', '.join(_ident(name) for name in names)}) "
            f"VALUES ({', '.join('%s' for _ in names)})"
        )
        if return_repr:
            sql += " RETURNING *"

        connection = self._connection()
        try:
            cursor = connection.execute(
                sql,
                tuple(self._adapt(row[name]) for name in names),
            )
            result = _rows(cursor) if return_repr else []
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upsert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str],
        action: ConflictAction,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        if not row:
            raise ValueError("upsert row cannot be empty")

        names = [str(name) for name in row]
        conflicts = tuple(str(name) for name in conflict_columns)
        if not conflicts:
            raise ValueError("upsert requires conflict columns")
        for name in names:
            _ident(name)
        for name in conflicts:
            _ident(name)
        if any(name not in row for name in conflicts):
            raise ValueError("conflict columns must be present in upsert row")

        sql = (
            f"INSERT INTO public.{_ident(table)} "
            f"({', '.join(_ident(name) for name in names)}) "
            f"VALUES ({', '.join('%s' for _ in names)}) "
            f"ON CONFLICT ({', '.join(_ident(name) for name in conflicts)}) "
        )
        update_names = [name for name in names if name not in conflicts]
        if action is ConflictAction.MERGE:
            if update_names:
                sql += "DO UPDATE SET " + ", ".join(
                    f"{_ident(name)} = EXCLUDED.{_ident(name)}"
                    for name in update_names
                )
            else:
                sql += "DO NOTHING"
        elif action is ConflictAction.IGNORE:
            sql += "DO NOTHING"
        else:
            raise ValueError(f"unsupported conflict action: {action!r}")

        if return_repr:
            sql += " RETURNING *"

        connection = self._connection()
        try:
            cursor = connection.execute(
                sql,
                tuple(self._adapt(row[name]) for name in names),
            )
            rows = _rows(cursor) if return_repr else []
            connection.commit()
            return rows
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def insert_ignore_conflicts(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str] = (),
        return_repr: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        if not row:
            raise ValueError("insert row cannot be empty")

        names = [str(name) for name in row]
        for name in names:
            _ident(name)
        conflicts = tuple(str(name) for name in conflict_columns)
        for name in conflicts:
            _ident(name)
        if any(name not in row for name in conflicts):
            raise ValueError("conflict columns must be present in insert row")

        sql = (
            f"INSERT INTO public.{_ident(table)} "
            f"({', '.join(_ident(name) for name in names)}) "
            f"VALUES ({', '.join('%s' for _ in names)}) "
        )
        if conflicts:
            sql += (
                f"ON CONFLICT ({', '.join(_ident(name) for name in conflicts)}) "
                "DO NOTHING"
            )
        else:
            sql += "ON CONFLICT DO NOTHING"
        if return_repr:
            sql += " RETURNING *"

        connection = self._connection()
        try:
            cursor = connection.execute(
                sql,
                tuple(self._adapt(row[name]) for name in names),
            )
            rows = _rows(cursor) if return_repr else []
            connection.commit()
            return rows
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def update(
        self,
        table: str,
        match: Mapping[str, object],
        values: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        if not match:
            raise ValueError("update requires match criteria")
        if not values:
            raise ValueError("update values cannot be empty")

        value_names = [str(name) for name in values]
        match_names = [str(name) for name in match]
        sql = (
            f"UPDATE public.{_ident(table)} SET "
            + ", ".join(f"{_ident(name)} = %s" for name in value_names)
            + " WHERE "
            + " AND ".join(f"{_ident(name)} = %s" for name in match_names)
            + " RETURNING *"
        )
        params = tuple(
            self._adapt(values[name])
            for name in value_names
        ) + tuple(
            self._adapt(match[name])
            for name in match_names
        )

        connection = self._connection()
        try:
            rows = _rows(connection.execute(sql, params))
            connection.commit()
            return rows
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete(
        self,
        table: str,
        match: Mapping[str, object],
    ) -> None:
        if not match:
            raise ValueError("delete requires match criteria")
        names = [str(name) for name in match]
        sql = (
            f"DELETE FROM public.{_ident(table)} WHERE "
            + " AND ".join(f"{_ident(name)} = %s" for name in names)
        )

        connection = self._connection()
        try:
            connection.execute(
                sql,
                tuple(self._adapt(match[name]) for name in names),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def rpc(
        self,
        name: str,
        params: Mapping[str, Any] | None = None,
    ) -> object:
        raise DataGatewayOperationUnsupported(
            f"EmpireDB RPC is not mapped: {name}"
        )
