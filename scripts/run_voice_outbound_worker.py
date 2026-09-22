#!/usr/bin/env python3
"""Bounded live business-phone worker for Empire Voice Lab."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
from typing import Any

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.call_manager import build_call_work
from empire_os.locale_intelligence import contact_window_status, resolve_locale
from empire_os.outbound_role_transport import SupabaseOutboundRpc
from empire_os.qualification_worker_v2 import request_json
from empire_os.voice_lab import EmpireVoiceLab
from empire_os.vonage_call_transport import (
    VonageCallConfig,
    VonageCallTransport,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire governed voice outbound")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--daily-cap", type=int, default=5)
    p.add_argument(
        "--mode",
        choices=("OBSERVE", "GUARDED_EXECUTE"),
        default=os.getenv("EMPIRE_PHONE_MODE", "OBSERVE"),
    )
    p.add_argument("--execute", action="store_true")
    return p


def _voice_intent(item: dict[str, Any], daily_cap: int) -> tuple[str, Any]:
    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    proposed = request_json(
        "POST",
        "/rest/v1/rpc/propose_call_ready_voice_intent",
        payload={
            "p_prospect_id": item["prospect_id"],
            "p_recipient": item["phone"],
            "p_idempotency_key": (
                f"voice:{item['prospect_id']}:{date_key}"
            ),
            "p_metadata": {
                "call_ready": True,
                "source": "buyer_deferred_enrichment",
                "priority_score": item.get("priority_score"),
                "reason": item.get("reason"),
                "timezone_governed": True,
                "actual_revenue": False,
                "voice_legal_basis": legal_basis,
                "line_type": line_type or None,
                "legal_basis_source": item.get("legal_basis_source"),
            },
        },
    )
    intent_id = str(
        (proposed or {}).get("intent_id") or ""
    ).strip()
    if not intent_id:
        raise RuntimeError("voice intent id missing")

    approved = request_json(
        "POST",
        "/rest/v1/rpc/auto_approve_voice_intent",
        payload={
            "p_intent_id": intent_id,
            "p_daily_cap": daily_cap,
        },
    )
    return intent_id, approved


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    limit = max(1, min(int(args.limit), 20))
    daily_cap = max(1, min(int(args.daily_cap), 20))
    execute = bool(args.execute and args.mode == "GUARDED_EXECUTE")

    provider = VonageCallTransport(VonageCallConfig.from_env())
    provider_ready = provider.config.readiness()
    voice_deps = EmpireVoiceLab.dependency_readiness()
    runtime_ready = bool(
        all(voice_deps.values())
        and provider_ready.get("execution_allowed") is True
    )

    work = build_call_work(limit=limit)
    sender_rpc = SupabaseOutboundRpc("empire_outbound_sender")
    queue = BuyerDeferredEnrichmentQueue()
    results: list[dict[str, Any]] = []

    for item in work.get("items") or []:
        locale = resolve_locale({"metro": item.get("metro")})
        window = contact_window_status(
            locale,
            start_hour=9,
            end_hour=17,
        )
        legal_basis = str(
            item.get("voice_legal_basis") or ""
        ).strip()
        line_type = str(item.get("line_type") or "").strip()
        record: dict[str, Any] = {
            "prospect_id": item.get("prospect_id"),
            "business_name": item.get("business_name"),
            "priority_score": item.get("priority_score"),
            "timezone": locale.timezone,
            "contact_window": window,
            "voice_legal_basis": legal_basis or None,
            "line_type": line_type or None,
            "legal_basis_source": item.get("legal_basis_source"),
            "executed": False,
        }
        if not legal_basis:
            record["decision"] = "HOLD_LEGAL_BASIS_UNVERIFIED"
            results.append(record)
            continue
        if (
            legal_basis == "verified_business_landline_b2b"
            and line_type not in {"landline", "landline_tollfree"}
        ):
            record["decision"] = "HOLD_BUSINESS_LANDLINE_UNVERIFIED"
            results.append(record)
            continue
        if legal_basis not in {
            "prior_express_written_consent",
            "verified_business_landline_b2b",
        }:
            record["decision"] = "HOLD_UNSUPPORTED_LEGAL_BASIS"
            results.append(record)
            continue
        if window.get("eligible") is not True:
            record["decision"] = "HOLD_CONTACT_WINDOW"
            results.append(record)
            continue
        if not execute:
            record["decision"] = "READY_FOR_GUARDED_EXECUTE"
            results.append(record)
            continue
        if not runtime_ready:
            record["decision"] = "HOLD_RUNTIME_NOT_READY"
            record["provider_readiness"] = provider_ready
            record["voice_dependencies"] = voice_deps
            results.append(record)
            continue

        intent_id = ""
        provider_call_id = ""
        claimed = False
        try:
            intent_id, approval = _voice_intent(item, daily_cap)
            record["intent_id"] = intent_id
            record["approval"] = approval

            claim = sender_rpc(
                "claim_outbound_send",
                {
                    "p_intent_id": intent_id,
                    "p_actor": "empire_voice_worker",
                },
            )
            claimed = True
            plan = {
                **item,
                "intent_id": intent_id,
                "prospect_id": item["prospect_id"],
                "phone": claim["recipient"],
                "execution_allowed": True,
            }
            provider_result = provider.create_call(
                plan,
                authorized=True,
            )
            raw = provider_result.get("provider_response") or {}
            provider_call_id = str(
                raw.get("uuid")
                or raw.get("conversation_uuid")
                or ""
            ).strip()
            if not provider_call_id:
                raise RuntimeError("Vonage call id missing")

            delivery = sender_rpc(
                "record_outbound_delivery",
                {
                    "p_intent_id": intent_id,
                    "p_event_type": "sent",
                    "p_actor": "empire_voice_worker",
                    "p_provider_message_id": provider_call_id,
                    "p_payload": {
                        "provider": "vonage",
                        "voice_engine": "empire_voice_lab",
                        "speech_vendor": None,
                        "daily_cap": daily_cap,
                    },
                },
            )
            queue.mark_call_attempted(
                str(item["prospect_id"]),
                intent_id=intent_id,
                provider_call_id=provider_call_id,
            )
            record.update({
                "decision": "CALL_ACCEPTED_BY_PROVIDER",
                "executed": True,
                "provider_call_id": provider_call_id,
                "delivery": delivery,
            })
        except Exception as exc:
            record["decision"] = "CALL_FAILED_CLOSED"
            record["error"] = f"{type(exc).__name__}:{str(exc)[:240]}"
            if intent_id and claimed:
                try:
                    sender_rpc(
                        "record_outbound_delivery",
                        {
                            "p_intent_id": intent_id,
                            "p_event_type": "failed",
                            "p_actor": "empire_voice_worker",
                            "p_provider_message_id": (
                                provider_call_id
                                or f"voice-attempt:{intent_id}"
                            ),
                            "p_payload": {
                                "provider": "vonage",
                                "voice_engine": "empire_voice_lab",
                                "error_type": type(exc).__name__,
                            },
                        },
                    )
                except Exception:
                    pass
        results.append(record)

    print(json.dumps({
        "mode": args.mode,
        "execute_requested": bool(args.execute),
        "execution_allowed": execute and runtime_ready,
        "runtime_ready": runtime_ready,
        "provider_readiness": provider_ready,
        "voice_dependencies": voice_deps,
        "queue_total": work.get("queue_total", 0),
        "selected": work.get("selected", 0),
        "daily_cap": daily_cap,
        "results": results,
        "actual_revenue": False,
        "terms_authority": False,
        "payment_authority": False,
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
        }), file=sys.stderr)
        raise SystemExit(2)
