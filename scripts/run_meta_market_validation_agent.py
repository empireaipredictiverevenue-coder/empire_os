#!/usr/bin/env python3
"""Own-scope agent tick: plan research, review permitted packets, write local status.

Never reads production secrets, initiates a network call or queues external action.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from empire_os.agents.meta_market_validation_agent import run_agent
from empire_os.agents.meta_market_priority_intelligence_v1 import build_video_research_prompts
from empire_os.agents.meta_muse_social_operations_v1 import build_muse_social_operations
from empire_os.agents.meta_muse_mcp_handoff_v1 import plan_muse_mcp_operations
from empire_os.agents.meta_muse_social_syndicate_v1 import build_owned_syndication_preview

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "runtime" / "meta_market_research_agent"


def _read_packet(path_str: str | None):
    if not path_str:
        return None
    path = Path(path_str).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError("invalid_or_oversized_evidence_packet")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_exchange_snapshot(path_str: str | None):
    """Bounded local canonical selection; never emit raw prospect or buyer rows."""
    if not path_str:
        return None
    source = Path(path_str)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 3_000_000:
        raise ValueError("untrusted_or_missing_canonical_selection_file")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_canonical_selection_shape")
    return data


def _safe_write(path: Path, obj: dict):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe_output_path")
    data = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    fd, tmp_path = tempfile.mkstemp(prefix=".meta_research_", dir=path.parent, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Empire Meta Market Validation Agent (OBSERVE)")
    parser.add_argument("--observations-file", help="Optional pre-authorised structured evidence packet")
    parser.add_argument("--report-only", action="store_true", help="Print result without writing local reports")
    parser.add_argument("--exchange-snapshot", help="Optional existing canonical OBSERVE snapshot, read only")
    parser.add_argument("--video-prompt-pack", action="store_true", help="Include independently authored video method prompts for founder review")
    parser.add_argument("--social-draft-niche", choices=("roofing","hvac","plumbing","dental","electrical"), help="Generate 14 days of organic Facebook/Instagram drafts")
    parser.add_argument("--social-draft-market", help="Target market for social plan, e.g. tampa, fl")
    parser.add_argument("--mcp-handoff", action="store_true", help="Add no-execution Metricool MCP capability handoff")
    parser.add_argument("--social-syndicate-preview", action="store_true", help="Create owned Facebook/Instagram variant queue; never publishes")
    args = parser.parse_args()
    packet = _read_packet(args.observations_file)
    exchange = _read_exchange_snapshot(args.exchange_snapshot)
    result = run_agent(evidence_packet=packet, exchange_snapshot=exchange)
    if args.video_prompt_pack:
        result["video_prompt_pack"] = {
            lane["lane_id"]: build_video_research_prompts(
                niche=lane["niche"], market=lane["city"].lower())
            for lane in result["lanes"]
        }
    if (args.mcp_handoff or args.social_syndicate_preview) and not args.social_draft_niche:
        parser.error("--mcp-handoff and --social-syndicate-preview require a --social-draft-niche and --social-draft-market")
    if args.social_draft_niche and not args.social_draft_market:
        parser.error("--social-draft-niche requires --social-draft-market")
    if args.social_draft_niche:
        social=build_muse_social_operations(niche=args.social_draft_niche,market=args.social_draft_market)
        result["social_operations_draft"]=social
        if args.social_syndicate_preview:
            result["owned_social_syndication_preview"]=build_owned_syndication_preview(social)
        if args.mcp_handoff:
            result["social_mcp_handoff"]=plan_muse_mcp_operations(social)
    if not args.report_only:
        if REPORT_DIR.is_symlink():
            raise ValueError("unsafe_report_directory")
        REPORT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        _safe_write(REPORT_DIR / "latest.json", result)
        _safe_write(REPORT_DIR / "research_tasks.json", {
            "owner": result["agent"], "mode": "OBSERVE",
            "external_execution": False,
            "tasks": [t for lane in result["lanes"] for t in lane["agent_tasks"]],
        })
        if args.social_syndicate_preview:
            _safe_write(
                REPORT_DIR / "owned_social_poster_queue.json",
                result["owned_social_syndication_preview"],
            )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
