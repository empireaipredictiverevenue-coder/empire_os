"""Run founder prompts into bounded B2B research and ASTRA review assignments."""
from __future__ import annotations
from typing import Any, Mapping
from empire_os.a2a_prompt_targeted_buyer_research_v1 import (
    compile_target_prompt, target_source_review,
)

SCHEMA = "empire.a2a.founder_targeting_cycle.v1"

def build_prompted_research(
    config: Mapping[str, Any], community: Mapping[str, Any],
) -> dict[str, Any]:
    if (not isinstance(config, Mapping)
            or config.get("schema_version") != "empire.a2a.founder_prompt_target_profiles.v1"
            or config.get("owner") != "empire.a2a.commercial_signal_miner.v1"
            or config.get("execution_authority") != "NONE"
            or config.get("contact_authorized") is not False
            or config.get("campaign_launch_authorized") is not False):
        raise ValueError("UNTRUSTED_FOUNDER_TARGETING_CONFIG")
    entries = config.get("profiles")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10:
        raise ValueError("PROFILE_COUNT_OUT_OF_RANGE")
    profiles = []
    seen = set()
    for item in entries:
        if not isinstance(item, Mapping) or not isinstance(item.get("label"), str):
            raise ValueError("BAD_PROFILE_LABEL")
        label = item["label"]
        if not 2 <= len(label) <= 80:
            raise ValueError("BAD_PROFILE_LABEL")
        spec = compile_target_prompt(item.get("prompt"))
        if spec["target_id"] in seen:
            raise ValueError("DUPLICATE_FOUNDER_TARGET")
        seen.add(spec["target_id"])
        review = target_source_review(spec, community) if spec["research_ready"] else {
            "status": "TARGET_CLARIFICATION_REQUIRED",
            "missing": spec["missing_details"],
            "source_count": 0,
            "research_reference_count": 0,
            "permitted_sources": [],
            "public_discussion_refs": [],
        }
        profiles.append({
            "label": label, "specification": spec,
            "source_review": review,
            "astra_agent_instructions_not_executed": {
                "role": "B2B_BUYER_AND_MARKET_RESEARCH_ANALYST",
                "instruction": (
                    "Search only pre-approved existing company and public research sources "
                    "for the exact specified niche, geographic service area, buyer type "
                    "and purchasing problem. Review each public reference; distinguish "
                    "hiring, tips and seller pitches from explicit business buying needs. "
                    "Verify source and permitted use, legal entity, canonical dedupe, "
                    "actual decision role, territory, product fit and stated capacity. "
                    "Never infer payment, buyer budget, consent, licence or qualified lead. "
                    "Hand evidence questions to the existing domain owner for review. "
                    "Do not contact, scrape private groups, publish, spend or pay."
                ),
                "target_id": spec["target_id"],
                "focus": {
                    "niche": spec["niche"], "metro": spec["metro"],
                    "offer": spec["product_type"],
                    "buyer_roles": spec["buyer_roles_to_verify"],
                    "exclusions": spec["negative_filters"],
                },
                "required_output_fields": [
                    "source_provenance", "research_observation",
                    "independent_company_validation_state", "market_fit_state",
                    "buying_intent_status", "owner_to_review",
                    "contact_permission_status", "product_delivery_rights_status",
                ],
                "allowed_autonomous_execution": "NONE",
            },
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "profile_count": len(profiles),
        "ready_for_permitted_source_review": sum(p["specification"]["research_ready"] for p in profiles),
        "targets_with_public_sources": sum(bool(p["source_review"]["source_count"]) for p in profiles),
        "profiles": profiles,
        "llm_prompting_ready_for_owner_integration": True,
        "live_llm_model_called": False, "external_source_fetches": 0,
        "new_prospects_promoted": 0,
        "qualified_leads_found": 0, "campaigns_launched": 0,
        "owner_agent_tasks_dispatched": 0,
        "founder_marketing_approval_used": False,
        "facebook_instagram_connected": False,
        "money_spent": 0, "external_messages_sent": 0,
    }
