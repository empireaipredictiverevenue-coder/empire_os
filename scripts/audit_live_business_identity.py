#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from empire_os.business_identity_actor import (
    run_business_identity_actor,
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

        observation = observation_from_signal(
            str(signal_id),
            signal,
        )

        if observation is None:
            continue

        intent = run_intent_brain_actor(
            observation
        )

        if (
            intent.get("decision")
            != "RESOLVE_IDENTITY"
        ):
            continue

        brain = (
            intent.get("output", {})
            .get("intent_brain", {})
        )

        request = {
            "upstream_decision":
                "RESOLVE_IDENTITY",
            "signal_id": str(signal_id),
            "source_url":
                observation.get("url"),
            "title":
                observation.get("title"),
            "text":
                observation.get("text"),
            "niche":
                brain.get("niche"),
            "metro":
                observation.get("metro"),
        }

        result = run_business_identity_actor(
            request
        )

        output = result.get("output") or {}

        rows.append({
            "signal":
                str(signal_id)[:12],
            "decision":
                result.get("decision"),
            "handle":
                output.get(
                    "source_handle"
                ),
            "person_names":
                output.get(
                    "source_person_names"
                ),
            "business_name":
                output.get(
                    "business_name"
                ),
            "website":
                output.get("website"),
            "verified":
                output.get(
                    "business_identity_verified"
                ),
            "candidate_count":
                output.get(
                    "candidate_count"
                ),
            "title":
                str(
                    observation.get(
                        "title"
                    )
                    or ""
                )[:100],
        })

    print(
        "live_candidate_count =",
        len(rows),
    )

    print(
        "business_identity_decisions =",
        dict(
            Counter(
                row["decision"]
                for row in rows
            )
        ),
    )

    verified = [
        row
        for row in rows
        if row["verified"] is True
    ]

    print(
        "verified_business_identity_count =",
        len(verified),
    )

    for row in rows:
        print(row)

    print()
    print(
        "outbound_sent = False"
    )
    print(
        "canonical_promotion = False"
    )
    print(
        "execution_authority = none"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
