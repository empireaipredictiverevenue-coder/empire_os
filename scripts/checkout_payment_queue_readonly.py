"""Read-only founder queue for existing DIRECT BSC checkout requests.

No customer PII, wallet addresses, secrets, database mutations, or approvals.
Operates only as the local postgres OS user, with fixed SQL and bounded output.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import pwd
import sys
from typing import Any

import psycopg

DSN = (
    "host=/var/run/postgresql port=5432 dbname=empiredb "
    "user=postgres connect_timeout=5"
)

SQL = """
SELECT id, fulfilment_order_id, amount_usdt, status,
       created_at, expires_at
FROM public.bsc_payment_requests
WHERE settlement_mode = 'direct'
  AND status IN ('pending','approved')
ORDER BY created_at DESC, id
LIMIT %s
"""


def summarize(rows: list[tuple], *, now: datetime) -> dict[str, Any]:
    results = []
    for request_id, order_id, amount, status, created, expires in rows:
        expired = bool(expires is None or expires <= now)
        results.append({
            "request_id": str(request_id),
            "order_id": str(order_id),
            "amount_usdt": str(amount),
            "status": status,
            "created_at": created.isoformat(),
            "expires_at": expires.isoformat() if expires else None,
            "expired": expired,
            "next_step": (
                "REVIEW_WITH_DEDICATED_OPERATOR"
                if status == "pending" and not expired else
                "SEND_APPROVED_INSTRUCTIONS_VIA_VERIFIED_BUYER_CHANNEL"
                if status == "approved" and not expired else
                "EXPIRED_HOLD_NO_PAYMENT_INSTRUCTIONS"
            ),
        })
    return {
        "mode": "READ_ONLY",
        "settlement_mode": "direct",
        "pending_review_count": sum(
            item["status"] == "pending" and not item["expired"]
            for item in results
        ),
        "approved_instruction_delivery_count": sum(
            item["status"] == "approved" and not item["expired"]
            for item in results
        ),
        "results": results,
        "customer_contact_data_disclosed": False,
        "payment_approved": False,
        "payment_executed": False,
        "actual_revenue": False,
    }


def main(argv: list[str] | None = None) -> int:
    values = sys.argv[1:] if argv is None else argv
    if values not in ([], ["--limit", "25"]):
        print('CHECKOUT_QUEUE_STATUS=BLOCKED_READONLY_ARGS_REQUIRED')
        return 2
    if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
        print('CHECKOUT_QUEUE_STATUS=BLOCKED_POSTGRES_OS_ID_REQUIRED')
        return 2
    try:
        with psycopg.connect(DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout='4000ms'")
                cursor.execute(
                    "SELECT current_database(), current_user, pg_is_in_recovery()"
                )
                if cursor.fetchone() != ("empiredb", "postgres", False):
                    raise RuntimeError("canonical DB identity unverified")
                cursor.execute(SQL, (25,))
                result = summarize(cursor.fetchall(), now=datetime.now(timezone.utc))
            connection.rollback()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({
            "status": "QUEUE_UNAVAILABLE_FAIL_CLOSED",
            "mode": "READ_ONLY",
            "customer_contact_data_disclosed": False,
            "payment_approved": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
