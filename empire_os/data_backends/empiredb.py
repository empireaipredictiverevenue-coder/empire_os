"""EmpireDB PostgreSQL provider for CanonicalDataGateway.

Internal compatibility provider only. It exposes bounded table CRUD with
identifier validation and parameterized values. Arbitrary SQL and generic RPC
execution are intentionally unsupported.
"""
from __future__ import annotations

from decimal import Decimal

import re
from typing import Any, Mapping, Sequence

from empire_os.data_values import JsonValue
from empire_os.canonical_data_gateway import DataGatewayOperationUnsupported
from empire_os.data_backends.postgres import PostgresConnector
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import ConflictAction, DataFilter, FilterOperator, OrderSpec
from empire_os.data_query import postgres_filter_column


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Explicit compatibility RPC surface. This mirrors only legacy service-role
# proposal/read authority. Sensitive approval, verifier, sender and revenue
# recognition functions remain available only through dedicated role transports.
_RPC_SQL_CASTS: dict[str, dict[str, str]] = {
    "ingest_prospect_atomic": {
        "p_prospect": "jsonb",
        "p_evidence": "jsonb",
        "p_ingest_key": "text",
        "p_identity_keys": "text[]",
    },
}


_RPC_PARAMS: dict[str, tuple[str, ...]] = {
    "propose_outbound_intent": (
        "p_entity_id", "p_prospect_id", "p_buyer_id", "p_opportunity_id",
        "p_channel", "p_recipient", "p_subject", "p_body_text", "p_body_html",
        "p_offer_key", "p_idempotency_key", "p_proposed_by", "p_expires_at",
        "p_metadata",
    ),
    "get_outbound_intent_review": ("p_intent_id",),
    "list_closer_work": ("p_limit",),
    "open_closer_case": ("p_reply_id",),
    "provision_buyer_from_closer_case": ("p_case_id", "p_actor"),
    "get_closer_reply_context": ("p_case_id", "p_reply_id"),
    "propose_closer_reply_intent": (
        "p_case_id", "p_reply_id", "p_subject", "p_body_text",
        "p_idempotency_key", "p_proposed_by", "p_expires_at",
    ),
    "record_buyer_capacity_intake": (
        "p_case_id", "p_reply_id", "p_territory", "p_daily_cap",
        "p_delivery_route", "p_delivery_reference", "p_evidence", "p_actor",
    ),
    "prepare_fulfilment_order_from_capacity": ("p_case_id", "p_actor"),
    "propose_commercial_evidence": (
        "p_evidence_kind", "p_buyer_id", "p_closer_case_id",
        "p_fulfilment_order_id", "p_niche", "p_metro", "p_amount_cents",
        "p_unit", "p_source_type", "p_source_reference", "p_evidence",
        "p_observed_at", "p_valid_until",
    ),
    "verify_commercial_evidence": ("p_evidence_id", "p_actor"),
    "reject_commercial_evidence": ("p_evidence_id", "p_actor", "p_reason"),
    "record_closer_recommendation": (
        "p_case_id", "p_type", "p_confidence", "p_rationale",
        "p_message", "p_model_key",
    ),
    "get_commercial_product_catalog": ("p_product_code", "p_limit"),
    "get_commercial_product_readiness": ("p_product_code",),
    "get_verified_terms_evidence": ("p_fulfilment_order_id",),
    "propose_commercial_terms": (
        "p_fulfilment_order_id", "p_price_cents", "p_acquisition_cost_cents",
        "p_fulfilment_cost_cents", "p_terms", "p_idempotency_key", "p_actor",
    ),
    "get_commercial_terms_review": ("p_review_id",),
    "propose_bsc_payment_request": (
        "p_fulfilment_order_id", "p_amount_usdt", "p_payer_address",
        "p_treasury_address", "p_min_block_number", "p_expires_at",
        "p_idempotency_key", "p_actor",
    ),
    "propose_bsc_escrow_request": (
        "p_fulfilment_order_id", "p_amount_usdt", "p_payer_address",
        "p_beneficiary_address", "p_min_block_number", "p_expires_at",
        "p_idempotency_key", "p_actor",
    ),
    "cancel_bsc_payment_request": ("p_request_id", "p_actor", "p_reason"),
    "get_commercial_outcome_feedback": ("p_limit",),
    "auto_review_buyer_candidate": ("p_review_id", "p_daily_cap"),
    "auto_verify_buyer_stated_commercial_evidence": ("p_evidence_id",),
    "auto_verify_commercial_product_version": ("p_version_id",),
    "ingest_prospect_atomic": (
        "p_prospect", "p_evidence", "p_ingest_key", "p_identity_keys",
    ),
    "list_auto_verifiable_commercial_evidence": ("p_limit",),
    "list_buyer_reviews_for_outbound": ("p_limit",),
    "list_due_outbound_followups": ("p_limit",),
    "propose_buyer_candidate_review": (
        "p_prospect_id", "p_entity_id", "p_contact_name", "p_contact_title",
        "p_contact_email", "p_offer_key", "p_company_score",
        "p_decision_score", "p_evidence", "p_idempotency_key",
    ),
    "propose_buyer_scout_candidate": (
        "p_domain", "p_business_name", "p_website", "p_description",
        "p_buyer_type", "p_direct_buyer_score",
        "p_explicit_direct_buyer_evidence", "p_target_buyer_pools",
        "p_target_product_codes", "p_target_corridor_keys", "p_query_evidence",
        "p_site_evidence", "p_provenance", "p_actor",
    ),
    "propose_call_ready_voice_intent": (
        "p_prospect_id", "p_recipient", "p_idempotency_key", "p_metadata",
    ),
    "propose_commercial_product_version": (
        "p_product_code", "p_billing_model", "p_currency", "p_price_basis",
        "p_acquisition_cost_basis", "p_fulfilment_cost_basis",
        "p_margin_policy", "p_provenance", "p_evidence_refs",
        "p_effective_from", "p_effective_until", "p_actor",
    ),
    "propose_outbound_followup": (
        "p_root_intent_id", "p_step", "p_subject", "p_body_text",
        "p_idempotency_key", "p_proposed_by", "p_expires_at",
    ),
    "propose_reviewed_outbound_intent": (
        "p_review_id", "p_subject", "p_body_text", "p_body_html",
        "p_idempotency_key", "p_proposed_by", "p_expires_at", "p_metadata",
    ),
    "record_voice_provider_event": (
        "p_intent_id", "p_external_call_id", "p_event_type", "p_payload",
    ),
    "record_voice_turn": (
        "p_intent_id", "p_external_call_id", "p_turn_index", "p_direction",
        "p_body_text", "p_evidence",
    ),
    "refresh_pending_buyer_candidate_review": (
        "p_review_id", "p_contact_name", "p_contact_title", "p_contact_email",
        "p_decision_score", "p_evidence",
    ),
    "register_commercial_product_identity": (
        "p_product_code", "p_product_name", "p_product_family",
        "p_billing_model", "p_configuration", "p_provenance", "p_actor",
    ),
}


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


_RPC_NUMERIC_PARAMS: dict[str, frozenset[str]] = {
    'propose_buyer_candidate_review': frozenset(('p_company_score', 'p_decision_score',)),
    'refresh_pending_buyer_candidate_review': frozenset(('p_decision_score',)),
}

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
            column = postgres_filter_column(item.column)
            if item.operator is FilterOperator.EQ:
                where_parts.append(f"{column} = %s")
                params.append(item.value)
            elif item.operator is FilterOperator.NE:
                where_parts.append(f"{column} <> %s")
                params.append(item.value)
            elif item.operator is FilterOperator.LIKE:
                where_parts.append(f"{column} LIKE %s")
                params.append(item.value)
            elif item.operator is FilterOperator.ILIKE:
                where_parts.append(f"{column} ILIKE %s")
                params.append(item.value)
            elif item.operator is FilterOperator.GTE:
                where_parts.append(f"{column} >= %s")
                params.append(item.value)
            elif item.operator is FilterOperator.IS_NULL:
                where_parts.append(f"{column} IS NULL")
            elif item.operator is FilterOperator.IS_NOT_NULL:
                where_parts.append(f"{column} IS NOT NULL")
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
        rpc_name = str(name or "").strip()
        keys = _RPC_PARAMS.get(rpc_name)
        if keys is None:
            raise DataGatewayOperationUnsupported(
                f"EmpireDB RPC is not mapped: {rpc_name}"
            )

        supplied = dict(params or {})
        if set(supplied) != set(keys):
            raise ValueError(
                f"EmpireDB RPC parameters do not match contract: {rpc_name}"
            )

        casts = _RPC_SQL_CASTS.get(rpc_name, {})
        placeholders = [
            f"%s::{casts[key]}" if key in casts else "%s"
            for key in keys
        ]
        sql = (
            f"SELECT public.{_ident(rpc_name)}("
            + ", ".join(placeholders)
            + ")"
        )
        # RPC parameters cross a PostgreSQL function-call boundary.
        # Structured Python values represent json/jsonb RPC arguments and
        # must never reach psycopg as raw dict/list objects.
        #
        # Keep scalar SQL values native; mark only structured RPC values
        # for the connector's canonical JSONB adapter.
        numeric_keys = _RPC_NUMERIC_PARAMS.get(
            rpc_name,
            frozenset(),
        )

        def adapt_rpc_parameter(key: str) -> Any:
            value = supplied[key]

            # Psycopg binds Python float as PostgreSQL double precision.
            # A PostgreSQL function declared with NUMERIC will therefore
            # fail overload resolution. Decimal binds as NUMERIC and
            # preserves exact score semantics.
            if key in numeric_keys and value is not None:
                if not isinstance(value, Decimal):
                    value = Decimal(str(value))

            if isinstance(value, dict):
                value = JsonValue(value)
            elif isinstance(value, list):
                # Most structured lists are JSONB, but RPC parameters
                # explicitly declared as SQL arrays must remain native lists
                # so psycopg binds them as PostgreSQL arrays.
                if casts.get(key, "").endswith("[]"):
                    value = [str(item) for item in value]
                else:
                    value = JsonValue(value)

            return self._adapt(value)

        values = tuple(
            adapt_rpc_parameter(key)
            for key in keys
        )

        connection = self._connection()
        try:
            cursor = connection.execute(sql, values)
            row = cursor.fetchone()
            if not row or len(row) != 1:
                raise RuntimeError(
                    f"EmpireDB RPC returned invalid shape: {rpc_name}"
                )
            connection.commit()
            return row[0]
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
