#!/usr/bin/env python3
"""Manual one-shot, fictional-only original PRIME local llama.cpp self-play.

The canonical loopback llama.cpp adapter is reused, never a separate model.
Only the named synthetic scenario is inspected, no Google/Gmail/CRM/provider
data; no autonomous scheduler, live API route, purchases or outbound.
"""
from __future__ import annotations

import argparse
import json

from empire_os.coder.llama_cpp_provider import LlamaCppProvider
from empire_os.digital_twin_conversation_local_selfplay import (
    SelfPlayBudget, rehearse_local_model_selfplay, cockpit_selfplay_shadow,
)
from scripts.rehearse_prime_conversation_digital_twin_20261024 import (
    default_scenarios, cross_sector_scenarios,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="pricing_resolution")
    parser.add_argument("--show-fictional-dialogue", action="store_true")
    parser.add_argument("--max-calls", type=int, default=2)
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=96)
    args = parser.parse_args()
    cases = {s.scenario_id: s for s in (
        default_scenarios() + cross_sector_scenarios()
    )}
    if args.scenario not in cases:
        parser.error("only existing fictional scenario identifiers accepted")
    budget = SelfPlayBudget(
        max_turns=args.max_turns,
        max_model_calls=args.max_calls,
        max_output_tokens_per_call=args.max_tokens,
        max_elapsed_seconds=36,
    )
    budget.validate()
    provider = LlamaCppProvider(
        base_url="http://127.0.0.1:11435", timeout_seconds=12,
        model="qwen2.5-coder:1.5b",
    )
    if not provider.health():
        print(json.dumps({
            "schema_version": "empire.prime.local_twin_cli_hold.v1",
            "status": "EXISTING_LOCAL_INFERENCE_UNAVAILABLE",
            "mode": "SIMULATION",
            "real_world_accuracy": None,
            "actual_revenue": False,
            "execution_authority": "none",
        }))
        return 2
    result = rehearse_local_model_selfplay(
        scenario=cases[args.scenario],
        inference=provider, budget=budget,
        show_fictional_dialogue=args.show_fictional_dialogue,
    )
    packet = {
        "owner": "ORIGINAL_EMPIREOS_PRIME_DIGITAL_TWIN",
        "purpose": "FICTIONAL_LOCAL_BUYER_SELLER_SELF_PLAY_RESEARCH",
        "cockpit_projection": cockpit_selfplay_shadow(result),
        "source_provider": "existing_loopback_llama_cpp",
        "production_integration_or_live_route_enabled": False,
        "live_buyer_emails_accessed": False,
        "real_world_accuracy": None,
        "money_moved": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
    if args.show_fictional_dialogue:
        packet["fictional_dialogue"] = result["fictional_dialogue"]
    print(json.dumps(packet, sort_keys=True, indent=2))
    # A source-model hold is a safe completed observation; never pretend pass.
    return 0 if result["status"] in {
        "SYNTHETIC_BUYER_SAYS_RESOLVED_NOT_VERIFIED",
        "SYNTHETIC_OPT_OUT_STOP", "SYNTHETIC_REFUSAL_STOP",
        "NO_RECOGNISED_SYNTHETIC_CONCERN",
        "SYNTHETIC_UNCLEAR_NOT_RESOLVED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
