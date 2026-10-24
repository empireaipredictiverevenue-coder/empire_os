#!/usr/bin/env python3
"""Run original Digital Twin / PRIME synthetic two-sided conversation gauntlet.

Completely offline; reads no original buyer, CRM or provider personal data.
Fictional scripted buyers and rule-governed fictional seller exchanges only.
"""
from __future__ import annotations

import argparse
import json

from empire_os.digital_twin_conversation_fractal_physics import (
    SyntheticChannelEnvelope, run_fractal_physics_gauntlet,
    founder_fractal_physics_status,
)
from empire_os.digital_twin_conversation_rehearsal import (
    SyntheticConversationScenario, run_conversation_twin_gauntlet,
    founder_conversation_twin_status,
)


def default_scenarios() -> tuple[SyntheticConversationScenario, ...]:
    S = SyntheticConversationScenario
    return (
        S("pricing_resolution", "How much does it cost?", "PRICE_OR_BUDGET_QUESTION",
          "CONFIRM_RESOLVED", "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
        S("trust_still_concerned", "Could you provide case studies and proof?",
          "TRUST_OR_PROOF_QUESTION", "STILL_CONCERNED", "REOPENED"),
        S("privacy_silence", "What is your GDPR and privacy policy?",
          "PRIVACY_OR_COMPLIANCE_CONCERN", "SILENCE",
          "ANSWERED_AWAITING_CONFIRMATION"),
        S("timing_decline", "Not ready yet. Maybe next quarter.",
          "TIMING_OR_CAPACITY_CONCERN", "DECLINE", "SIMULATED_DECLINED"),
        S("scope_reopened", "What exactly do we get in the package?",
          "SCOPE_OR_FIT_QUESTION", "REOPEN_AFTER_CONFIRM", "REOPENED"),
        S("implementation_accepted", "Please explain the implementation steps.",
          "INTEGRATION_OR_IMPLEMENTATION_CONCERN", "CONFIRM_RESOLVED",
          "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
        S("attribution_unresolved", "How is call tracking and buyer leg connection verified?",
          "ATTRIBUTION_OR_DELIVERY_CONCERN", "STILL_CONCERNED", "REOPENED"),
        S("team_approval", "We need approval from our team.",
          "DECISION_AUTHORITY_QUESTION", "CONFIRM_RESOLVED",
          "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
        S("explicit_optout", "Please unsubscribe me. Do not contact me again.",
          None, "OPT_OUT", "SIMULATED_OPTED_OUT"),
        S("generic_thanks", "Thanks for the update.",
          None, "SILENCE", "NO_OBJECTION_OBSERVED"),
        S("unsupported_guarantee_blocked", "What exactly do we get?",
          "SCOPE_OR_FIT_QUESTION", "SILENCE",
          "SELLER_RESPONSE_POLICY_HELD",
          seller_response_override="We guarantee 100% conversion."),
    )


def cross_sector_scenarios() -> tuple[SyntheticConversationScenario, ...]:
    """Fictional multi-sector tests; no actual market/customer evidence."""
    S = SyntheticConversationScenario
    return (
        S("finance_forecast_proof", "Can you provide proof for a financial forecast?",
          "TRUST_OR_PROOF_QUESTION", "STILL_CONCERNED", "REOPENED"),
        S("logistics_onboarding", "What is the implementation plan for freight onboarding?",
          "INTEGRATION_OR_IMPLEMENTATION_CONCERN", "CONFIRM_RESOLVED",
          "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
        S("travel_product_scope", "What exactly do we get in the hotel data scope?",
          "SCOPE_OR_FIT_QUESTION", "SILENCE", "ANSWERED_AWAITING_CONFIRMATION"),
        S("legal_case_privacy", "What are the GDPR and privacy requirements for legal intake?",
          "PRIVACY_OR_COMPLIANCE_CONCERN", "DECLINE", "SIMULATED_DECLINED"),
        S("energy_solar_attribution", "How does solar call tracking and attribution work?",
          "ATTRIBUTION_OR_DELIVERY_CONCERN", "REOPEN_AFTER_CONFIRM", "REOPENED"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-synthetic-dialogue", action="store_true")
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--fractal-depth", type=int, default=2)
    parser.add_argument("--channel-latency-ms", type=int, default=60)
    parser.add_argument("--channel-timeout-ms", type=int, default=3000)
    parser.add_argument("--synthetic-seed", type=int, default=101)
    parser.add_argument("--cross-sector", action="store_true",
                        help="run five fictional finance, logistics, travel, legal, and energy cases")
    parser.add_argument("--all", action="store_true",
                        help="run all sixteen fictional cases together")
    args = parser.parse_args()
    if args.all and args.cross_sector:
        parser.error("choose --all or --cross-sector, not both")
    scenarios = (default_scenarios() + cross_sector_scenarios() if args.all
                 else cross_sector_scenarios() if args.cross_sector
                 else default_scenarios())
    if args.scenario is not None:
        scenarios = tuple(s for s in scenarios if s.scenario_id == args.scenario)
        if not scenarios:
            parser.error("unknown synthetic scenario")
    report = run_conversation_twin_gauntlet(
        scenarios, show_dialogue=args.show_synthetic_dialogue,
    )
    summary = founder_conversation_twin_status(report)
    fractal = run_fractal_physics_gauntlet(
        scenarios, max_depth=args.fractal_depth,
        envelope=SyntheticChannelEnvelope(
            one_way_latency_ms=args.channel_latency_ms,
            timeout_budget_ms=args.channel_timeout_ms,
            seed=args.synthetic_seed,
        ),
    )
    fractal_founder = founder_fractal_physics_status(fractal)
    print(json.dumps({
        "owner": "ORIGINAL_DIGITAL_TWIN_AND_PRIME",
        "run": summary,
        "fractal_physics": fractal_founder,
        "fractal_transport_assumption": "Synthetic message latency/dropout, not physical law of emotion",
        "scenarios": report["scenarios"],
        "real_world_validation_established": False,
        "original_provider_contact_tenant_connected": False,
        "simulated_sales_are_not_economic_revenue": True,
    }, indent=2, sort_keys=True))
    return 0 if report["all_scenario_contracts_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
