#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from empire_os.first_party_identity_actor import (
    run_first_party_identity_actor,
)
from empire_os.intent_brain_actor import (
    run_intent_brain_actor,
)
from empire_os.signal_intent_actor_router import (
    observation_from_signal,
)


INBOX = Path(
    "/srv/empire_os/runtime/acquisition/"
    "signal_inbox.json"
)


def main() -> int:
    signals = json.loads(
        INBOX.read_text(encoding="utf-8")
    )

    rows = []

    for signal_id, signal in signals.items():
        if not isinstance(signal, dict):
            continue

        if not str(
            signal.get("source") or ""
        ).endswith("_intent"):
            continue

        payload = observation_from_signal(
            str(signal_id),
            signal,
        )

        if payload is None:
            continue

        intent = run_intent_brain_actor(
            payload
        )

        if intent.get("decision") != "RESOLVE_IDENTITY":
            continue

        # Use only explicitly observed identity anchors.
        # Never infer a company/domain from the social URL.
        business_name = str(
            payload.get("business_name")
            or payload.get("company_name")
            or ""
        ).strip()

        website = str(
            payload.get("business_url")
            or payload.get("company_url")
            or payload.get("website")
            or ""
        ).strip()

        verified = (
            payload.get("first_party_verified")
            is True
            or payload.get(
                "canonical_identity_verified"
            )
            is True
        )

        identity_request = {
            "upstream_decision": "RESOLVE_IDENTITY",
            "signal_id": str(signal_id),
            "business_name": business_name,
            "website": website,
            "first_party_site_verified": verified,
            "metro": str(
                payload.get("metro") or ""
            ),
            "niche": str(
                (
                    intent.get("output")
                    or {}
                ).get(
                    "commercial_state",
                    {},
                ).get("niche")
                or ""
            ),
        }

        # This audit will never perform network recovery
        # unless a verified business+website anchor already
        # exists in the durable observation.
        result = run_first_party_identity_actor(
            identity_request
        )

        rows.append({
            "signal": str(signal_id)[:12],
            "title": str(
                payload.get("title") or ""
            )[:120],
            "business_name":
                business_name or None,
            "website": website or None,
            "site_verified": verified,
            "identity_decision":
                result.get("decision"),
            "next":
                result.get(
                    "recommended_next_action"
                ),
        })

    print("candidate_count =", len(rows))

    print(
        "identity_decisions =",
        dict(
            Counter(
                row["identity_decision"]
                for row in rows
            )
        ),
    )

    for row in rows:
        print(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
