"""Rollback-only EmpireDB functional commercial canary.

Exercises the governed commercial path under the real empiredb_app role:
buyer + prospect canary rows -> evidence registration -> evidence verification ->
buyer activation -> atomic allocation -> commercial event verification.

The transaction is always rolled back. No canary row is committed and this
module has no cutover authority.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


class CanaryFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryFailure(message)


def run_canary(dsn: str) -> dict[str, Any]:
    buyer_id = uuid.uuid4()
    prospect_id = uuid.uuid4()
    allocation_key = f"empiredb-canary:{uuid.uuid4()}"
    evidence_reference = f"rollback-canary:{uuid.uuid4()}"
    niche = "__empiredb_canary_niche__"
    metro = "__empiredb_canary_metro__"
    agreement_hash = "a" * 64

    report: dict[str, Any] = {
        "schema_version": "empire.empiredb-functional-canary.v1",
        "rollback_only": True,
        "canonical_backend_unchanged": True,
        "production_cutover_authority": False,
    }

    connection = psycopg.connect(
        dsn,
        connect_timeout=5,
        application_name="empiredb-functional-canary",
    )
    try:
        connection.execute("BEGIN")
        connection.execute("SET LOCAL statement_timeout = '60s'")

        connection.execute(
            """
            INSERT INTO public.buyers (
                id, buyer_name, niche, metro, status, is_active,
                daily_cap, calls_today, monthly_retainer, per_call_fee,
                commercial_activation_state
            )
            VALUES (
                %s, %s, %s, %s, 'prospective', false,
                3, 0, 0, 0, 'discovered'
            )
            """,
            (
                buyer_id,
                "__empiredb_rollback_canary_buyer__",
                niche,
                metro,
            ),
        )

        connection.execute(
            """
            INSERT INTO public.prospects (
                id, business_name, niche, metro, status
            )
            VALUES (%s, %s, %s, %s, 'new')
            """,
            (
                prospect_id,
                "__empiredb_rollback_canary_prospect__",
                niche,
                metro,
            ),
        )

        evidence_id = connection.execute(
            """
            SELECT public.register_buyer_commercial_evidence(
                %s, 'signed_agreement', %s, %s, %s,
                3, 1250, '+10000000000', NULL,
                %s::jsonb
            )
            """,
            (
                buyer_id,
                evidence_reference,
                niche,
                metro,
                Jsonb({
                    "agreement_sha256": agreement_hash,
                    "agreement_effective_at": "2026-09-27T00:00:00Z",
                    "canary": "rollback_only",
                }),
            ),
        ).fetchone()[0]
        _require(evidence_id is not None, "evidence registration returned no id")

        verified = connection.execute(
            "SELECT public.verify_buyer_commercial_evidence(%s, %s)",
            (evidence_id, "empiredb.functional_canary"),
        ).fetchone()[0]
        _require(
            verified.get("decision") in {"verified", "existing_verification"},
            f"unexpected evidence verification decision: {verified}",
        )

        activated = connection.execute(
            "SELECT public.activate_buyer_from_evidence(%s, %s)",
            (evidence_id, "empiredb.functional_canary"),
        ).fetchone()[0]
        _require(
            activated.get("decision") in {"activated", "existing_activation"},
            f"unexpected buyer activation decision: {activated}",
        )

        buyer_state = connection.execute(
            """
            SELECT commercial_activation_state, status, is_active,
                   daily_cap, calls_today, per_lead_rate,
                   commercial_terms_source, commercial_terms_reference,
                   commercial_terms_verified_at IS NOT NULL,
                   capacity_verified_at IS NOT NULL,
                   delivery_verified_at IS NOT NULL
            FROM public.buyers
            WHERE id = %s
            """,
            (buyer_id,),
        ).fetchone()
        _require(buyer_state is not None, "activated buyer row missing")
        _require(buyer_state[0] == "activated", "buyer did not activate")
        _require(str(buyer_state[1]).lower() == "active", "buyer status not active")
        _require(bool(buyer_state[2]), "buyer is_active is false")
        _require(int(buyer_state[3]) == 3, "buyer daily_cap mismatch")
        _require(str(buyer_state[6]) == "signed_agreement", "terms source mismatch")
        _require(str(buyer_state[7]) == evidence_reference, "terms reference mismatch")
        _require(all(bool(v) for v in buyer_state[8:11]), "activation timestamps incomplete")

        allocation = connection.execute(
            """
            SELECT public.allocate_prospect_atomic(
                %s, %s, %s::jsonb, %s
            )
            """,
            (
                prospect_id,
                allocation_key,
                Jsonb([{
                    "buyer_id": str(buyer_id),
                    "match_score": 0.9876,
                }]),
                "empiredb.functional_canary",
            ),
        ).fetchone()[0]
        _require(
            allocation.get("decision") == "allocated",
            f"allocation did not succeed: {allocation}",
        )
        _require(
            str(allocation.get("buyer_id")) == str(buyer_id),
            "allocation buyer mismatch",
        )
        _require(
            str(allocation.get("prospect_id")) == str(prospect_id),
            "allocation prospect mismatch",
        )

        order_id = allocation.get("fulfilment_order_id")
        _require(order_id is not None, "allocation returned no fulfilment order")

        order = connection.execute(
            """
            SELECT state, buyer_id, prospect_id, allocation_key
            FROM public.fulfilment_orders
            WHERE id = %s
            """,
            (order_id,),
        ).fetchone()
        _require(order is not None, "fulfilment order missing")
        _require(order[0] == "matched", "fulfilment order not matched")
        _require(str(order[1]) == str(buyer_id), "order buyer mismatch")
        _require(str(order[2]) == str(prospect_id), "order prospect mismatch")
        _require(order[3] == allocation_key, "allocation key mismatch")

        event_count = connection.execute(
            """
            SELECT count(*)
            FROM public.commercial_events
            WHERE buyer_id = %s
              AND event_type IN (
                  'buyer_commercially_activated',
                  'prospect_allocated'
              )
            """,
            (buyer_id,),
        ).fetchone()[0]
        _require(int(event_count) == 2, f"expected 2 commercial events, got {event_count}")

        calls_today = connection.execute(
            "SELECT calls_today FROM public.buyers WHERE id = %s",
            (buyer_id,),
        ).fetchone()[0]
        _require(int(calls_today) == 1, "allocation did not consume one capacity slot")

        report.update({
            "evidence_registered": True,
            "evidence_verified": True,
            "buyer_activated": True,
            "prospect_allocated": True,
            "commercial_events_verified": 2,
            "capacity_increment_verified": True,
            "verified": True,
        })
        return report
    finally:
        connection.rollback()
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    report = run_canary(dsn)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
