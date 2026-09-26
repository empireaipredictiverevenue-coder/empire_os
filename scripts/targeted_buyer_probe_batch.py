#!/usr/bin/env python3
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import urllib.parse

from empire_os.buyer_probe_worker import rejection_reason, run
from empire_os.qualification_worker_v2 import request_json

TARGET_IDS = (
    "ab6369f5-143d-4311-9781-405d74a1996a",
    "e9f3aa93-b51b-496e-9041-3c861c8db593",
    "b1cd9f23-f8d1-49ba-8b83-ca318b7a0f23",
    "2324c644-2fb6-4e53-a76c-7ac39d6ac281",
    "c1690f29-d3df-42e1-a1fe-ed15f437506a",
    "8ce4ef57-e7d4-4120-8c33-40f01f9d338c",
    "0bb37688-7d4f-4f72-94da-7433aba7ce5b",
    "cfdf420e-5155-461e-acb5-9043fed7ab07",
    "c4001188-2712-4a25-a002-bb5b9a95860e",
    "af19be95-07e2-41a7-a83f-7b2b144855b4",
    "45279d1f-5639-406c-a334-afd7533e07ad",
    "86a2681d-f7a3-4b18-970b-7eb327ca9d74",
    "50d71f07-1ed4-4e7a-b880-7b2d33b821cb",
    "e5214c6e-72bf-43ce-9150-6502c6bc4223",
    "4d3a023b-d0f6-4168-b77b-6e42220d0cbe",
    "e81a0342-0e9e-4bed-ab50-80168bc436e9",
)

OUTPUT = Path("/srv/empire_os/runtime/buyer_probe_targeted/latest.json")


def _fetch() -> list[dict]:
    select = ",".join(
        (
            "id",
            "business_name",
            "niche",
            "metro",
            "phone",
            "website",
            "buy_signal_score",
            "status",
            "notes",
            "contact_name",
            "contact_title",
            "contact_source",
            "created_at",
        )
    )
    params = urllib.parse.urlencode(
        {
            "select": select,
            "id": f"in.({','.join(TARGET_IDS)})",
        }
    )
    rows = request_json("GET", f"/rest/v1/prospects?{params}") or []
    return [row for row in rows if isinstance(row, dict)]


def _probe(row: dict) -> dict:
    try:
        result = run(
            row,
            max_pages=9,
            request_timeout=4.0,
            time_budget_seconds=14.0,
        )
        result["rejection_reason"] = rejection_reason(result)
        return result
    except Exception as exc:
        return {
            "prospect_id": row.get("id"),
            "business_name": row.get("business_name"),
            "error": f"{type(exc).__name__}:{str(exc)[:240]}",
        }


def main() -> int:
    rows = _fetch()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_probe, row) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(
        key=lambda row: (
            row.get("outreach_ready") is not True,
            str(row.get("business_name") or ""),
        )
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str) + "\n"
    )

    for row in results:
        print(
            json.dumps(
                {
                    key: row.get(key)
                    for key in (
                        "prospect_id",
                        "business_name",
                        "review_ready",
                        "outreach_ready",
                        "preferred_email",
                        "rejection_reason",
                        "error",
                    )
                },
                default=str,
            )
        )
    print(
        json.dumps(
            {
                "ready": sum(
                    1
                    for row in results
                    if row.get("outreach_ready") is True
                ),
                "total": len(results),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
