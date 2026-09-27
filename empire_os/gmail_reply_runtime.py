"""Runtime bridge from a normalized Gmail message to canonical reply ingest.

This module performs no Gmail network access and cannot send mail. It resolves
the canonical sent intent by Gmail thread id through the existing guarded
Supabase transport, then delegates to gmail_reply_adapter for correlation,
inert ingest, and deterministic classification.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote

from empire_os.gmail_reply_adapter import ingest_gmail_reply
from empire_os.outbound_role_transport import SupabaseOutboundRpc
from empire_os.qualification_worker_v2 import request_json

Request = Callable[..., Any]


def list_canonical_gmail_intents(
    thread_id: str,
    *,
    request_factory: Request | None = None,
) -> list[dict[str, Any]]:
    """Return at most two sent Gmail intents for ambiguity detection."""
    normalized = str(thread_id or "").strip()
    if not normalized:
        return []
    request = request_factory or request_json
    encoded = quote(normalized, safe="")
    rows = request(
        "GET",
        "/rest/v1/outbound_intents"
        "?select=id,channel,recipient,normalized_recipient,status,metadata"
        "&channel=eq.email"
        "&status=eq.sent"
        "&metadata->>provider=eq.gmail"
        f"&metadata->>gmail_thread_id=eq.{encoded}"
        "&limit=2",
    ) or []
    if not isinstance(rows, list):
        raise ValueError("outbound intent projection must be a list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def process_gmail_message(
    message: Mapping[str, Any],
    *,
    self_addresses: Iterable[str] = (),
    request_factory: Request | None = None,
    reply_rpc: Callable[[str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Resolve, ingest and classify one normalized Gmail message safely."""
    thread_id = str(message.get("thread_id") or "").strip()
    if not thread_id:
        return {
            "ok": True,
            "ignored": True,
            "reason": "missing_thread_id",
            "outbound_sent": False,
            "actual_revenue": False,
        }

    request = request_factory or request_json
    intents = list_canonical_gmail_intents(
        thread_id,
        request_factory=request,
    )
    rpc = reply_rpc or SupabaseOutboundRpc(
        "empire_reply_ingest",
        request_factory=request,
    )
    return ingest_gmail_reply(
        message,
        intents,
        rpc,
        self_addresses=self_addresses,
    )
