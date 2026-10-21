"""Bounded advisory critique through Empire's existing loopback compute adapter.

The model receives only source titles/headings and literal topic signals.
Model suggestions are untrusted and can NEVER self-approve any research
claim, customer message, financial action or data resale.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Callable, Mapping
import json

from .brokerage_editorial_review import triage_local_model_draft


def challenge_research_brief(
    brief: Mapping,
    *,
    model_fn: Callable[[str], str] | None = None,
) -> dict:
    if not isinstance(brief, Mapping) or not isinstance(
        brief.get("evidence_ledger"), list
    ):
        raise ValueError("ORIGINAL_MARKET_EVIDENCE_BRIEF_REQUIRED")
    country = brief.get("country")
    if country not in ("GB", "US"):
        raise ValueError("SUPPORTED_RESEARCH_MARKET_REQUIRED")
    observations = []
    for row in brief["evidence_ledger"][:8]:
        if not isinstance(row, Mapping) or row.get("inspected") is not True:
            continue
        host = str(row.get("publisher_host") or "")[:130]
        terms = ", ".join(str(t)[:45] for t in
                          (row.get("literal_terms_seen_on_page_not_clinically_validated") or [])[:8])
        observations.append(host + " | observed literal terms: " + terms)
    if len(observations) < 2:
        return {
            "status": "HELD_INSUFFICIENT_ORIGINAL_SOURCES_FOR_MODEL",
            "model_called": False,
            "independent_facts_approved": False,
            "customer_use_authorized": False,
        }
    if model_fn is None:
        return {
            "status": "LOCAL_MODEL_NOT_CALLED",
            "model_called": False,
            "independent_facts_approved": False,
            "customer_use_authorized": False,
        }
    question = (
        "You are a critical, sceptical analyst for private editorial review. "
        "Using only the source observations below, write at most 3 short "
        "questions a human should investigate next. Never infer rankings, "
        "patients, clinical quality, available appointments, sales, market "
        "demand or client revenue from webpage terms. Do not recommend "
        "contacting anyone. Do not claim editorial approval.\nMarket: "
        + country + "\n" + "\n".join(observations)
    )
    try:
        draft = model_fn(question)
        if not isinstance(draft, str):
            raise ValueError("MODEL_NON_TEXT_OUTPUT")
        draft = draft[:1200]
    except Exception:
        return {
            "status": "HELD_LOCAL_MODEL_UNAVAILABLE",
            "model_called": True,
            "independent_facts_approved": False,
            "customer_use_authorized": False,
        }
    # The existing provider's chat() returns a JSON error string on
    # inference timeout rather than raising. Never classify it as research.
    try:
        returned = json.loads(draft)
    except (ValueError, TypeError):
        returned = None
    if (isinstance(returned, dict) and returned.get("error")
        or draft.strip().startswith(("llama_cpp_request_failed:",
                                     "llama_cpp_invalid_response"))):
        return {
            "status": "HELD_LOCAL_MODEL_PROVIDER_REPORTED_ERROR",
            "model_called": True,
            "independent_facts_approved": False,
            "customer_use_authorized": False,
            "outbound_authorized": False,
        }
    check = triage_local_model_draft(draft)
    rejected = check.get("unsupported_outcome_inference_detected") is True
    return {
        "status": ("HELD_MODEL_CONCLUSION_CONTRADICTS_SOURCE_LIMITS"
                   if rejected else
                   "UNTRUSTED_MODEL_EDITORIAL_QUESTIONS_ONLY"),
        "model_called": True,
        "proposed_questions_unverified": None if rejected else draft,
        "model_response_sha256": sha256(draft.encode()).hexdigest(),
        "source_content_is_independently_verified": False,
        "model_is_reviewer_or_editorial_authority": False,
        "independent_facts_approved": False,
        "customer_use_authorized": False,
        "outbound_authorized": False,
    }


def default_local_compute_challenge(prompt: str) -> str:
    """Reuse already running on-host llama.cpp provider, no new inference API."""
    from empire_os.coder.llama_cpp_provider import LlamaCppProvider
    provider = LlamaCppProvider(
        base_url="http://127.0.0.1:11435", timeout_seconds=30,
        model="qwen2.5-coder:1.5b",
    )
    if provider.health() is not True:
        raise ValueError("EXISTING_LOOPBACK_COMPUTE_UNAVAILABLE")
    return provider.chat(
        [{"role": "user", "content": prompt}],
        system=("You are an evidence-bound research critic. "
                "Ask only questions about missing evidence."),
        temperature=0,
        max_tokens=220,
    )
