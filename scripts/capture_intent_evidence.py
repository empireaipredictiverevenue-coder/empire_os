#!/usr/bin/env python3
"""Capture one public intent discovery into Empire's durable signal inbox.

Input is JSON on stdin. This command records evidence only. It never creates a
canonical prospect, sends outreach, accepts terms, or grants execution authority.

Example input:
{
  "source": "public_web",
  "url": "https://public.example/post/123",
  "title": "Need more qualified appointments",
  "text": "We need more leads and paid search is not consistently profitable.",
  "niche": "roofing",
  "metro": "US",
  "evidence_urls": ["https://business.example/landing-page"]
}
"""
from __future__ import annotations

import json
import sys

from empire_os.community_intent import capture_external_intent_evidence


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({
            "ok": False,
            "error": f"invalid_json:{exc.msg}",
            "execution_authority": "none",
        }, sort_keys=True))
        return 2

    if not isinstance(payload, dict):
        print(json.dumps({
            "ok": False,
            "error": "input_must_be_json_object",
            "execution_authority": "none",
        }, sort_keys=True))
        return 2

    try:
        result = capture_external_intent_evidence(**payload)
    except (TypeError, ValueError) as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "execution_authority": "none",
        }, sort_keys=True))
        return 2

    print(json.dumps({
        "ok": True,
        **result,
        "canonical_prospect_created": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
