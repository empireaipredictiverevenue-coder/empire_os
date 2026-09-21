#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from empire_os.conversation_recovery import (
    build_conversation_recovery,
    parse_delivered_events,
)
from empire_os.qualification_worker_v2 import request_json

ROOT = Path("/srv/empire_os")
OUT = ROOT / "runtime" / "conversation_recovery" / "latest.json"


def _get(path: str, params: dict[str, object]):
    query = urllib.parse.urlencode(params)
    value = request_json("GET", f"{path}?{query}") or []
    return value if isinstance(value, list) else []


def main() -> int:
    intents = _get(
        "/rest/v1/outbound_intents",
        {
            "select": "id,prospect_id,recipient,subject,status,metadata",
            "channel": "eq.email",
            "status": "eq.delivered",
            "order": "created_at.asc",
            "limit": 100,
        },
    )
    intent_ids = [
        str(row.get("id")) for row in intents if row.get("id")
    ]
    events = []
    if intent_ids:
        events = _get(
            "/rest/v1/outbound_events",
            {
                "select": "intent_id,event_type,occurred_at",
                "intent_id": f"in.({','.join(intent_ids)})",
                "event_type": "eq.delivered",
                "order": "occurred_at.asc",
                "limit": 300,
            },
        )

    prospect_ids = sorted({
        str(row.get("prospect_id"))
        for row in intents if row.get("prospect_id")
    })
    prospect_rows = []
    if prospect_ids:
        prospect_rows = _get(
            "/rest/v1/prospects",
            {
                "select": (
                    "id,business_name,niche,metro,rating,review_count,"
                    "buy_signal_score,runs_ads"
                ),
                "id": f"in.({','.join(prospect_ids)})",
                "limit": 200,
            },
        )
    prospects = {
        str(row.get("id")): row
        for row in prospect_rows
        if row.get("id")
    }

    payload = build_conversation_recovery(
        intents,
        parse_delivered_events(events),
        prospects,
        now=datetime.now(timezone.utc),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUT)
    print(json.dumps({
        key: payload[key]
        for key in (
            "delivered_first_touches",
            "due_now",
            "due_within_24h",
            "recoverable",
            "blocked_missing_context",
            "legacy_generic_subjects",
            "next_due_in_hours",
        )
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
