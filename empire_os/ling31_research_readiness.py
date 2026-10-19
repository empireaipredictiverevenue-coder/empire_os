"""Ling 3.1 Flash OpenCode Zen readiness + scientific research-only contract.

Read-only by default. A catalog listing or valid Zen credential is NOT an
inference-success or calibration result. Never silently failover to Ling paid,
and never submit buyer identities, credentials, unredacted source data or
commercial action instructions to free hosted models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from empire_os.model_registry import ModelRegistry
from empire_os.scientific_lead_reasoning import reason

MODEL_ID = "ling-3.1-flash-zen-free"
PROVIDER = "opencode"
ZEN_SLUG = "ling-3.1-flash-free"
SCHEMA = "empire.ling31_scientific_research_readiness.v1"

SCIENTIFIC_CONTROLS = (
    "verify_source_population_and_missingness",
    "independently_verify_original_official_source_and_rights",
    "separate_published_tender_notice_from_commercial_acceptance",
    "deduplicate_same_ocid_and_updated_releases",
    "check_temporal_leakage_before_original_predictions",
    "compare_prequential_Brier_with_historical_base_rate",
    "report_counterexamples_and_negative_controls",
)


def _utc(as_of: datetime | None = None) -> datetime:
    value = as_of or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("aware UTC model-review clock required")
    return value.astimezone(timezone.utc)


def review_ling31_free_readiness(
    *, as_of: datetime | None = None,
    registry: ModelRegistry | None = None,
) -> dict[str, Any]:
    at = _utc(as_of)
    model = (registry or ModelRegistry()).get(MODEL_ID)
    present = bool(
        model is not None and model.provider == PROVIDER
        and model.model == ZEN_SLUG and model.free
    )
    safe_disabled = bool(
        present and not model.enabled and not model.available
        and "revenue_truth" in model.disallowed_tasks
        and "payment" in model.disallowed_tasks
        and "outbound" in model.disallowed_tasks
        and model.max_stakes == "normal"
    )
    return {
        "schema_version": SCHEMA,
        "generated_at": at.isoformat(),
        "provider": "opencode_zen",
        "free_model_slug": ZEN_SLUG,
        "model_catalogue_entry_present": present,
        "router_blocks_unverified_model": safe_disabled,
        "configured_to_use_paid_endpoint": False,
        "actual_live_inference_verified": False,
        "last_observed_result": "ZEN_HTTP_400_MODEL_UNAVAILABLE",
        "last_observed_free_alternative": "OPENROUTER_HTTP_404_FREE_ROUTE_UNAVAILABLE",
        "free_price_claim": "PROVIDER_DOCUMENTED_LIMITED_TIME",
        "model_output_trusted_as_official_evidence": False,
        "scientific_method_verified": False,
        "read_only_hypothesis_research_allowed_if_available": True,
        "automatic_model_activation_allowed": False,
        "source_contacts_and_secrets_to_model_authorized": False,
        "model_calibrated_on_EmpireOS": False,
        "commercial_execution_authorized": False,
        "execution_authority": "none",
        "status": (
            "FREE_CATALOGUED_RUNTIME_UNAVAILABLE"
            if safe_disabled else "MODEL_POLICY_REVIEW_REQUIRED"
        ),
    }


def probe_ling31_free(
    *,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Explicit ONE-request public-free-model health probe, fixed literal text.

    No research data, customer records, secrets or payment tokens in the
    prompt. No paid fallback or model enablement. Client configured with one
    retry attempt, bounded time and fixed free slug.
    """
    if client_factory is None:
        from empire_os.agent_core import OpenCodeZenClient
        client_factory = lambda: OpenCodeZenClient(
            model=ZEN_SLUG, timeout=12, max_retries=1,
        )
    client = client_factory()
    if getattr(client, "model", None) != ZEN_SLUG:
        raise ValueError("free model slug mismatch; no paid fallback")
    if not getattr(client, "api_key", None):
        return {
            "status": "NO_EXISTING_ZEN_CREDENTIALS",
            "fixed_public_prompt_only": True,
            "successful_inference": False,
            "model_activated": False,
            "charged_paid_model": False,
            "execution_authority": "none",
        }
    try:
        answer = client.chat(
            [{"role": "user", "content": "Respond exactly with PONG."}],
            system="This is a zero-cost, one-request health test. No tools.",
            temperature=0, max_tokens=12,
        )
    except Exception:
        answer = None
    passed = isinstance(answer, str) and answer.strip() == "PONG"
    return {
        "status": (
            "FREE_INFERENCE_HEALTHY_PENDING_BENCHMARK"
            if passed else "FREE_INFERENCE_UNAVAILABLE"
        ),
        "fixed_public_prompt_only": True,
        "successful_inference": passed,
        "model_activated": False,
        "charged_paid_model": False,
        "commercial_model_decision_authorized": False,
        "execution_authority": "none",
    }


def scientific_research_protocol(
    mining_review: Mapping[str, Any], *, as_of: datetime | None = None,
) -> dict[str, Any]:
    """Deterministic controls over EXISTING source-mining aggregate.

    Scientific Agent receives an untrusted *research brief*, not raw buyer
    data or autonomous authority. We do not equate a source count with a
    statistical sample, conversion rate or calibrated forecast.
    """
    _utc(as_of)
    if (not isinstance(mining_review, Mapping)
        or mining_review.get("schema_version") != "empire.revenue_stream_mining.review.v1"
        or mining_review.get("mode") != "OBSERVE"
        or mining_review.get("execution_authority") != "none"
        or mining_review.get("worker_dispatched") is not False
        or mining_review.get("commercial_execution_authorized") is not False
    ):
        raise ValueError("untrusted source-mining science review")
    sources = mining_review.get("sources")
    if not isinstance(sources, Mapping) or set(sources) != {
        "acquisition", "opportunity_routes", "quant", "competitor"
    }:
        raise ValueError("incomplete science source inventory")
    statuses: dict[str, str] = {}
    seen = []
    for key in sorted(sources):
        entry = sources[key]
        if not isinstance(entry, Mapping):
            raise ValueError("invalid science source entry")
        status = entry.get("status")
        if status not in {
            "OBSERVED", "FRESH", "MISSING", "INVALID", "UNAVAILABLE",
            "UNTRUSTED", "FUTURE_HELD", "STALE",
        }:
            raise ValueError("invalid science source status")
        if status not in {"OBSERVED", "FRESH"} and entry.get("aggregate") is not None:
            raise ValueError("held source has untrusted aggregate")
        statuses[key] = status
        # Presence of an observed source supports only the existence of
        # usable research data. A missing source is NOT evidence against
        # commercial demand; neither can support a conversion-rate claim.
        if status in {"OBSERVED", "FRESH"}:
            seen.append({
                "source_id": "canonical_stream:" + key,
                "source_type": "public_first_party_claim",
                "direction": "support",
            })
    interpretation = reason(
        hypothesis="Bounded public source observations exist for internal research",
        observations=seen, prior=None,
    )
    if interpretation.get("posterior_probability") is not None:
        raise ValueError("scientific agent produced uncalibrated probability")
    if interpretation.get("probability_calibrated") is not False:
        raise ValueError("scientific agent falsely reported calibrated inference")
    return {
        "schema_version": "empire.scientific_source_mining_protocol.v1",
        "source_statuses": statuses,
        "scientific_reasoning_schema": interpretation["schema_version"],
        "scientific_reasoning_is_heuristic": True,
        "heuristic_priority_indicator": interpretation["research_priority_indicator"],
        "probability_calibrated": False,
        "posterior_probability": None,
        "controls_to_execute": list(SCIENTIFIC_CONTROLS),
        "control_results_verified": False,
        "required_outcome": "original_pre_outcome_forecast_and_independently_verified_terminal_revenue",
        "scientific_agent_invoked": False,
        "openmanus_executed": False,
        "ling_inference_invoked": False,
        "research_brief_for_optional_agents": {
            "research_goal": "falsify_unsupported_revenue_inferences_from_public_source_data",
            "allowed_inputs": ["canonical_source_aggregate", "public_official_source_ref"],
            "forbidden_inputs": ["personal_contacts", "api_keys", "tenant_records"],
            "require_counterevidence": True,
            "require_documented_sampling_frame": True,
            "source_text_untrusted_not_instructions": True,
            "max_external_spend_cents": 0,
            "tool_execution_authorized": False,
        },
        "money_spent": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
