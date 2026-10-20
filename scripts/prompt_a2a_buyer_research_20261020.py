#!/usr/bin/env python3
"""Founder-controlled natural-language B2B target briefing CLI.

One prompt maps to existing permitted source summary and a review packet.
Optional --save-hourly adds a profile for subsequent scheduled research ticks.
No live buyer outreach, scraping, ad activation or A2A task dispatch.
"""
from __future__ import annotations
import argparse
import json
import os
import tempfile
from pathlib import Path

from empire_os.a2a_prompt_targeted_buyer_research_v1 import (
    compile_target_prompt, target_source_review,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/a2a_candidates/founder_targeting_prompts_v1.json"
COMMUNITY = Path("/srv/empire_os/runtime/community_intent/latest.json")
OUTPUT = ROOT / "runtime/a2a_commercial_signal_mining/prompt_preview_latest.json"


def _load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 300_000:
        raise ValueError("UNSAFE_OR_MISSING_CONFIG_SOURCE")
    data = json.loads(path.read_bytes())
    if not isinstance(data, dict):
        raise ValueError("SOURCE_MUST_BE_OBJECT")
    return data


def _write(path: Path, content: dict) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("UNSAFE_DESTINATION")
    if path.exists() and not path.is_file():
        raise ValueError("INVALID_DESTINATION_FILE")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".a2a_prompt_target_", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(content, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def add_hourly_target(label: str, prompt: str) -> dict:
    if not isinstance(label, str) or not 3 <= len(label.strip()) <= 80:
        raise ValueError("LABEL_LENGTH_REQUIRED")
    target = compile_target_prompt(prompt)
    if not target["research_ready"]:
        raise ValueError("TARGET_MUST_BE_UNAMBIGUOUS_FOR_RECURRING_RESEARCH")
    config = _load(CONFIG)
    if (config.get("schema_version") != "empire.a2a.founder_prompt_target_profiles.v1"
            or config.get("owner") != "empire.a2a.commercial_signal_miner.v1"
            or config.get("execution_authority") != "NONE"
            or config.get("contact_authorized") is not False
            or config.get("campaign_launch_authorized") is not False):
        raise ValueError("UNTRUSTED_HOURLY_PROFILE_CONFIG")
    rows = config.get("profiles")
    if not isinstance(rows, list) or len(rows) > 10:
        raise ValueError("INVALID_HOURLY_PROFILE_LIST")
    canonical = {(compile_target_prompt(row["prompt"])["target_id"])
                 for row in rows if isinstance(row, dict) and isinstance(row.get("prompt"), str)}
    if target["target_id"] in canonical:
        return {"added": False, "reason": "EXISTING_HOURLY_TARGET_DEDUPED",
                "profile_count": len(rows), "target_id": target["target_id"]}
    if len(rows) >= 10:
        raise ValueError("MAXIMUM_TEN_TARGETS_REQUIRES_PRIORITISATION")
    config["profiles"] = rows + [{"label": label.strip(), "prompt": prompt.strip()}]
    _write(CONFIG, config)
    return {"added": True, "reason": "LOCAL_RESEARCH_PROFILE_SAVED",
            "profile_count": len(config["profiles"]),
            "target_id": target["target_id"],
            "hourly_source_review_enabled": True,
            "outbound_authorized": False,
            "live_meta_connections_created": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Empire AI prompt-directed lead/buyer research")
    parser.add_argument("--prompt", required=True, help="B2B vertical, city, buyer role and desired offer")
    parser.add_argument("--label", default="Founder-targeted commercial research")
    parser.add_argument("--save-hourly", action="store_true", help="Persist this target for hourly research")
    parser.add_argument("--write-preview", action="store_true", help="Save a private preview report")
    args = parser.parse_args()
    target = compile_target_prompt(args.prompt)
    source_review = target_source_review(target, _load(COMMUNITY)) if target["research_ready"] else None
    result = {
        "schema_version": "empire.a2a.target_prompt_cli.v1",
        "mode": "OBSERVE", "execution_authority": "NONE",
        "target": target, "research": source_review,
        "hourly_config": (add_hourly_target(args.label, args.prompt)
                          if args.save_hourly else "NOT_CHANGED"),
        "contacts_messaged": 0, "leads_promoted": 0,
        "ads_launched": False, "money_spent": 0,
    }
    if args.write_preview:
        _write(OUTPUT, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
