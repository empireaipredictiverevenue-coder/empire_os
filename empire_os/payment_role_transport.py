"""Direct PostgreSQL transport for separated payment roles.

Credentials are supplied only through a DSN at runtime. This module does not create,
store, print, or derive database passwords. Login roles must be members of exactly
one NOLOGIN permission role and use SET LOCAL ROLE inside each transaction.
"""
from __future__ import annotations

from typing import Any, Callable

from empire_os.payment_governance import PaymentGovernanceError

ROLE_FUNCTIONS = {
    "empire_payment_approver": {
        "get_bsc_payment_request_review": (
            "select public.get_bsc_payment_request_review(%s)",
            ("p_request_id",),
        ),
        "approve_bsc_payment_request": (
            "select public.approve_bsc_payment_request(%s,%s,%s)",
            ("p_request_id", "p_approved_by", "p_approval_note"),
        ),
        "cancel_bsc_payment_request": (
            "select public.cancel_bsc_payment_request(%s,%s,%s)",
            ("p_request_id", "p_actor", "p_reason"),
        ),
    },
    "empire_escrow_verifier": {
        "get_bsc_escrow_request_review": (
            "select public.get_bsc_escrow_request_review(%s)",
            ("p_request_id",),
        ),
        "record_bsc_escrow_creation": (
            "select public.record_bsc_escrow_creation(%s,%s::jsonb)",
            ("p_request_id", "p_evidence"),
        ),
        "record_bsc_escrow_lifecycle": (
            "select public.record_bsc_escrow_lifecycle(%s,%s,%s::jsonb)",
            ("p_agreement_id", "p_action", "p_evidence"),
        ),
    },
    "empire_bsc_verifier": {
        "get_bsc_payment_request_review": (
            "select public.get_bsc_payment_request_review(%s)",
            ("p_request_id",),
        ),
        "record_bsc_payment_evidence": (
            "select public.record_bsc_payment_evidence(%s,%s::jsonb)",
            ("p_request_id", "p_evidence"),
        ),
    },
}

class PostgresRoleRpc:
    def __init__(self, dsn: str, role: str, *, connect_factory: Callable | None = None):
        self.dsn = str(dsn or "").strip()
        self.role = role
        if not self.dsn:
            raise PaymentGovernanceError("dedicated database DSN required")
        if role not in ROLE_FUNCTIONS:
            raise PaymentGovernanceError("unsupported payment database role")
        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise PaymentGovernanceError(
                    "psycopg is required for dedicated payment role transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        allowed = ROLE_FUNCTIONS[self.role]
        if name not in allowed:
            raise PaymentGovernanceError(
                f"{self.role} is not allowed to execute {name}"
            )
        sql, keys = allowed[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise PaymentGovernanceError("unexpected dedicated-role RPC parameters")
        values = []
        for key in keys:
            value = params[key]
            if key == "p_evidence":
                import json
                value = json.dumps(value, separators=(",", ":"), sort_keys=True)
            values.append(value)
        role_sql = "SET LOCAL ROLE " + self.role
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(role_sql)
                    cursor.execute(sql, tuple(values))
                    row = cursor.fetchone()
        except Exception as exc:
            raise PaymentGovernanceError("dedicated payment database RPC failed") from exc
        if not row or len(row) != 1:
            raise PaymentGovernanceError("dedicated payment database RPC returned no result")
        return row[0]
