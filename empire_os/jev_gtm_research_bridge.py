"""JEV evidence-gap research using the *shared* Empire research core.

The research engine was independently implemented in the isolated
Vane/OpenManus/Odysseus intake; here it is reused under ASTRA/JEV policy.
Public observations are not canonical CRM, original mailbox proof, buyer
intent, consent, or economic outcomes. No unattended execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from empire_os.research.research_profiles import (
    ResearchProfile, build_research_plan, research_with_profile,
)

SCHEMA = "empire.jev.evidence_gap_research.v1"
POLICY = "jev_research_bridge_20261014_v1"
PUBLIC_GAPS = frozenset({
    "fresh_evidenced_signal_missing",
    "contradictory_signal_requires_review",
    "independent_evidence_required",
})
CANONICAL_GAPS = frozenset({
    "canonical_identity_or_tenant_binding_unverified",
    "suppression_readback_missing",
    "contact_suppressed",
})
ALLOWED_PROFILES = frozenset({"speed", "balanced", "quality"})
ALLOWED_LANES = ("official", "web", "company")
_MAX_SOURCES = 12


def _public(value: Any, *, max_len: int = 90) -> str:
    """Do not put emails, URLs, phone strings, or secret-ish input in queries."""
    if not isinstance(value, str):
        return ""
    candidate = " ".join(value.strip().split())
    if (not candidate or len(candidate) > max_len or
            "@" in candidate or "://" in candidate or
            re.search(r"[^a-zA-Z0-9 .,()/&'-]", candidate) or
            re.search(r"\b(?:api[_-]?key|password|token|secret)\b", candidate, re.I)):
        return ""
    return candidate


def _request_identity(decision: Mapping[str, Any]) -> tuple[str, str, str, str]:
    if not isinstance(decision, Mapping) or (
        decision.get("schema_version") != "empire.jev.gtm_decision.v2"
        or decision.get("mode") != "OBSERVE"
        or decision.get("execution_authority") != "none"
        or decision.get("recommendation_only") is not True
        or decision.get("outbound_approved") is not False
        or decision.get("contact_permission_granted") is not False
    ):
        raise ValueError("trusted shape of non-executing JEV decision required")
    identities = []
    for field in ("tenant_id", "entity_id", "opportunity_key", "decision_fingerprint"):
        value = decision.get(field)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 128:
            raise ValueError("complete JEV identity and decision fingerprint required")
        identities.append(value.strip())
    if not re.fullmatch(r"[0-9a-f]{64}", identities[3]):
        raise ValueError("JEV decision fingerprint malformed")
    return tuple(identities)  # type: ignore[return-value]


def plan_jev_evidence_gap(
    decision: Mapping[str, Any], *,
    public_niche: str,
    public_market: str,
    country: str = "GB",
    depth: str = "speed",
) -> dict[str, Any]:
    """Build deterministic bounded plan; canonical-only gaps are not web-fixable.

    Inputs public_niche/market must be already approved for *public* research.
    No named recipient, company email, tenant or prospect ID enters the query.
    """
    tenant, entity, opportunity, digest = _request_identity(decision)
    if depth not in ALLOWED_PROFILES:
        raise ValueError("unsupported JEV research depth")
    niche = _public(public_niche)
    market = _public(public_market)
    blockers = decision.get("blockers")
    if (not isinstance(blockers, (list, tuple)) or
            len(blockers) > 30 or
            any(not isinstance(b, str) or len(b) > 128 for b in blockers)):
        raise ValueError("bounded JEV blockers required")
    missing = sorted(set(blockers))
    canonical_pending = sorted(set(missing) & CANONICAL_GAPS)
    no_public_context = not niche or not market
    suppressed = decision.get("contact_suppressed") is True or "contact_suppressed" in missing
    public_pending = sorted(set(missing) & PUBLIC_GAPS)
    if (not public_pending and decision.get("next_research_action") in (
        "collect_dated_buyer_signal", "resolve_contradictory_signal"
    )):
        public_pending = ["fresh_evidenced_signal_missing"]
    # Review-only public market research can still happen with suppressed
    # contacts, but it must never produce a named-recipient research packet.
    scope = "MARKET_ONLY" if suppressed else "PUBLIC_MARKET_RESEARCH"
    blocked = no_public_context or not public_pending
    focus = (
        "independent dated public sources and contradicting evidence"
        if "contradictory_signal_requires_review" in public_pending
        else "current public market procurement funding hiring and expansion signals"
    )
    question = f"{niche} {market} {focus}" if not no_public_context else ""
    profile = ResearchProfile(
        mode=depth, lanes=ALLOWED_LANES, country=country,
        sector=niche,
    )
    # Validate the selected depth/country even for an empty research plan.
    limits = profile.validate()
    common = {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "policy_version": POLICY,
        "tenant_id": tenant, "entity_id": entity,
        "opportunity_key": opportunity, "decision_fingerprint": digest,
        "scope": scope, "canonical_authority_blockers": canonical_pending,
        "public_evidence_blockers": public_pending,
        "research_is_not_canonical_proof": True,
        "original_provider_authentication_verified": False,
        "contact_clearance_verified": False,
        "buyer_intent_verified": False,
        "commercial_economics_verified": False,
        "outbound_approved": False, "paid_api_budget_gbp": 0,
        "execution_authority": "none",
    }
    context = {"niche": niche, "market": market, "country": country, "depth": depth}
    plan_key = json.dumps(
        {"policy": POLICY, "decision": digest, "context": context,
         "canonical": canonical_pending, "public": public_pending},
        sort_keys=True, separators=(",", ":"),
    )
    common["plan_fingerprint"] = sha256(plan_key.encode()).hexdigest()
    if blocked:
        return {
            **common,
            "status": "BLOCKED_PUBLIC_CONTEXT_MISSING"
            if no_public_context else "CANONICAL_OR_NO_PUBLIC_EVIDENCE_GAP",
            "reason": "no approved public niche/market" if no_public_context
            else "source authority or commercial review cannot be repaired by web research",
            "query_plan": None, "question": None,
            "budget": {"max_queries": 0, "max_pages": 0},
        }
    public_plan = build_research_plan(question, profile)
    if (public_plan["execution_authority"] != "none"
            or public_plan["outbound_authorized"] is not False
            or public_plan["database_write"] is not False):
        raise ValueError("unsafe research planner")
    return {
        **common, "status": "PLANNED_PUBLIC_RESEARCH",
        "reason": "bounded public evidence gap investigation",
        "question": question,
        "query_plan": public_plan,
        "budget": {"max_queries": limits.max_queries, "max_pages": limits.max_pages},
    }


def run_jev_evidence_gap(
    decision: Mapping[str, Any], *,
    public_niche: str,
    public_market: str,
    search_fn: Callable[..., Mapping[str, Any]],
    inspect_fn: Callable[[str], Mapping[str, Any]],
    country: str = "GB",
    depth: str = "speed",
    follow_up_fn: Callable[[str, list[dict[str, Any]], list[str]], Sequence[str]] | None = None,
    synthesize_fn: Callable[[str, list[dict[str, Any]]], Mapping[str, Any]] | None = None,
    official_source_urls: Sequence[str] = (),
    source_only: bool = False,
) -> dict[str, Any]:
    """Explicit operator run; no default network/tool access or privileged ops.

    Reject caller-supplied plan and recompute from canonical-shaped JEV
    decision. Search/inspection must be independently configured as governed,
    public-only callbacks by the privileged host.
    """
    plan = plan_jev_evidence_gap(
        decision, public_niche=public_niche, public_market=public_market,
        country=country, depth=depth,
    )
    if plan["status"] != "PLANNED_PUBLIC_RESEARCH":
        return {
            "schema_version": "empire.jev.evidence_gap_receipt.v1",
            "status": plan["status"],
            "mode": "OBSERVE", "plan_fingerprint": plan["plan_fingerprint"],
            "decision_fingerprint": plan["decision_fingerprint"],
            "source_count": 0, "inspected_source_count": 0,
            "sources": [], "claims_unverified": [],
            "research_steps": [], "canonical_authority_blockers": plan["canonical_authority_blockers"],
            "public_evidence_blockers": plan["public_evidence_blockers"],
            "canonical_decision_modified": False,
            "commercial_promotion_authorized": False,
            "outbound_sent": False, "database_write": False,
            "execution_authority": "none",
        }
    if not callable(search_fn) or not callable(inspect_fn):
        raise ValueError("governed search and inspector callbacks required")
    # Explicit primary URLs must originate from an approved operator packet.
    # Never guess a document URL, treat a search-result page as a fact, or
    # silently widen this to arbitrary third-party websites.
    from empire_os.research.deep_research_intake import _public_url
    if not isinstance(official_source_urls, (tuple, list)) or len(official_source_urls) > 3:
        raise ValueError("bounded official primary source list required")
    if type(source_only) is not bool or (source_only and not official_source_urls):
        raise ValueError("source-only inspection needs explicit primary URLs")
    vetted: list[str] = []
    for url in official_source_urls:
        if not isinstance(url, str) or _public_url(url) != url or not url.startswith("https://"):
            raise ValueError("invalid official primary source URL")
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if not (host == "gov.uk" or host.endswith(".gov.uk")
                or host == "ons.gov.uk" or host.endswith(".ons.gov.uk")):
            raise ValueError("official first-party domain required")
        if url in vetted:
            raise ValueError("duplicate official primary URL")
        vetted.append(url)
    profile = ResearchProfile(
        mode=depth, lanes=ALLOWED_LANES,
        country=country, sector=_public(public_niche),
    )
    result = research_with_profile(
        plan["question"], profile=profile,
        search_fn=search_fn, inspect_fn=inspect_fn,
        follow_up_fn=follow_up_fn, synthesize_fn=synthesize_fn,
        operator_primary_urls=tuple(vetted),
        skip_discovery=source_only,
    )
    if (result.get("execution_authority") != "none"
            or result.get("outbound_authorized") is not False
            or result.get("database_write") is not False
            or result.get("claimed_commercial_authority") is not False):
        raise ValueError("research engine attempted commercial authority")
    evidence = result.get("evidence")
    if not isinstance(evidence, Mapping) or (
        evidence.get("execution_authority") != "none"
        or evidence.get("database_write") is not False
        or evidence.get("outbound_sent") is not False
        or evidence.get("outbound_authorized") is not False
    ):
        raise ValueError("unsafe research evidence result")
    rows = evidence.get("source_observations")
    if not isinstance(rows, list) or len(rows) > _MAX_SOURCES:
        raise ValueError("unbounded research source count")
    sources: list[dict[str, Any]] = []
    eligible: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("malformed research source")
        sid = raw.get("source_id")
        url = raw.get("url")
        if (not isinstance(sid, str) or not re.fullmatch(r"S[1-9][0-9]?", sid)
                or any(s["source_id"] == sid for s in sources)
                or not isinstance(url, str) or not url.startswith(("https://", "http://"))):
            raise ValueError("research provenance missing")
        # Check URLs are not private syntax even if the untrusted return value
        # bypassed the shared discovery normalizer.
        from empire_os.research.deep_research_intake import _public_url
        canonical = _public_url(url)
        if canonical != url:
            raise ValueError("unsafe source url")
        origin = raw.get("observation_type")
        if origin not in {"public_search_result", "operator_supplied_primary_source"}:
            raise ValueError("unknown original research source origin")
        if source_only and origin != "operator_supplied_primary_source":
            raise ValueError("unexpected discovery result during source-only review")
        if origin == "operator_supplied_primary_source" and url not in vetted:
            raise ValueError("operator source missing from approved set")
        inspected = raw.get("original_page_inspected") is True
        proof = raw.get("content_sha256")
        if inspected and (
            raw.get("inspection_status") != "ORIGINAL_HTML_HEADINGS_INSPECTED"
            or not isinstance(proof, str)
            or not re.fullmatch(r"[0-9a-f]{64}", proof)
        ):
            raise ValueError("original page provenance invalid")
        if inspected:
            eligible.add(sid)
        sources.append({
            "source_id": sid, "url": url,
            "host": urlsplit(url).hostname,
            "observation_type": origin,
            "content_sha256": proof if inspected else None,
            "original_page_inspected": inspected,
            "inspection_status": str(raw.get("inspection_status") or "UNAVAILABLE")[:90],
            "claim_accuracy_verified": False,
            "buyer_identity_verified": False,
        })
    claims: list[dict[str, Any]] = []
    for claim in evidence.get("draft_claims", []):
        if not isinstance(claim, Mapping):
            raise ValueError("invalid draft research claim")
        refs = claim.get("source_ids")
        if (not isinstance(refs, list) or not refs
                or any(sid not in eligible for sid in refs)):
            raise ValueError("unsupported cited claim")
        statement = claim.get("claim")
        if not isinstance(statement, str) or len(statement) > 1000:
            raise ValueError("invalid research claim")
        # Do not expose generated claim text in operator packets; only
        # evidence source refs and status until independently fact checked.
        claims.append({
            "source_ids": list(dict.fromkeys(refs)),
            "claim_sha256": sha256(statement.encode()).hexdigest(),
            "factual_accuracy_verified": False,
        })
    if len(claims) > 20:
        raise ValueError("unbounded draft claims")
    budget = evidence.get("budget") or {}
    if (not isinstance(budget, Mapping)
            or not 0 <= budget.get("searches_executed", -1) <= plan["budget"]["max_queries"]
            or not 0 <= budget.get("pages_considered", -1) <= plan["budget"]["max_pages"]):
        raise ValueError("research budget exceeded")
    steps = result.get("steps")
    if not isinstance(steps, list) or len(steps) != 6:
        raise ValueError("research step receipt invalid")
    actual_steps = {str(s.get("id")): str(s.get("status"))
                    for s in steps if isinstance(s, Mapping)}
    if set(actual_steps) != {"plan", "discover", "inspect", "crosscheck", "synthesize", "commercial"}:
        raise ValueError("research step receipt incomplete")
    if actual_steps["commercial"] != "blocked":
        raise ValueError("commercial step must remain blocked")
    receipt = {
        "schema_version": "empire.jev.evidence_gap_receipt.v1",
        "mode": "OBSERVE",
        "status": result.get("status"),
        "plan_fingerprint": plan["plan_fingerprint"],
        "decision_fingerprint": plan["decision_fingerprint"],
        "source_count": len(sources),
        "inspected_source_count": len(eligible),
        "sources": sources, "claims_unverified": claims,
        "research_steps": [{"id": key, "status": actual_steps[key]}
                           for key in ("plan", "discover", "inspect", "crosscheck", "synthesize", "commercial")],
        "canonical_authority_blockers": plan["canonical_authority_blockers"],
        "public_evidence_blockers": plan["public_evidence_blockers"],
        "searches_executed": budget["searches_executed"],
        "pages_considered": budget["pages_considered"],
        "source_discovery_disabled": source_only,
        "operator_primary_sources_attempted": len(vetted),
        "sources_are_public_observations_only": True,
        "original_provider_authentication_verified": False,
        "buyer_intent_verified": False,
        "contact_clearance_verified": False,
        "canonical_decision_modified": False,
        "commercial_promotion_authorized": False,
        "outbound_sent": False, "database_write": False,
        "execution_authority": "none",
    }
    return receipt


def inspect_jev_official_source(url: str) -> dict[str, Any]:
    """Use the existing pinned-IP, TLS-validated first-party research inspector.

    A single explicit source read, no redirects or crawling. Caller still
    owns legal/robots review and source factual confirmation. Never use
    generic shell/browser tools as an inspection fallback.
    """
    from empire_os.research.deep_research_intake import _public_url
    if not isinstance(url, str) or _public_url(url) != url or not url.startswith("https://"):
        return {"status": "UNSAFE_URL_REJECTED"}
    host = (urlsplit(url).hostname or "").lower()
    if not (host == "gov.uk" or host.endswith(".gov.uk")
            or host == "ons.gov.uk" or host.endswith(".ons.gov.uk")):
        return {"status": "NON_OFFICIAL_SOURCE_REJECTED"}
    from empire_os.research.public_page_inspector import inspect_public_html
    return inspect_public_html(url, timeout=5.0)


def run_jev_official_source_review(
    decision: Mapping[str, Any], *, public_niche: str,
    public_market: str, official_source_urls: Sequence[str],
    inspector: Callable[[str], Mapping[str, Any]] | None = None,
    country: str = "GB",
) -> dict[str, Any]:
    """Primary-only operator review with zero search-provider calls.

    Optional inspector only for offline test injection; this adapter is never
    installed as an unattended production route.
    """
    return run_jev_evidence_gap(
        decision, public_niche=public_niche, public_market=public_market,
        search_fn=lambda query, num: {"organic": [], "error": "DISCOVERY_DISABLED"},
        inspect_fn=inspector or inspect_jev_official_source,
        official_source_urls=official_source_urls,
        source_only=True,
        country=country,
        depth="speed",
    )


def attach_jev_research_review(
    decision: Mapping[str, Any], receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Annotate original JEV decision without re-ranking or elevating authority."""
    _, _, _, digest = _request_identity(decision)
    if (not isinstance(receipt, Mapping)
            or receipt.get("schema_version") != "empire.jev.evidence_gap_receipt.v1"
            or receipt.get("decision_fingerprint") != digest
            or receipt.get("execution_authority") != "none"
            or receipt.get("commercial_promotion_authorized") is not False
            or receipt.get("canonical_decision_modified") is not False
            or receipt.get("outbound_sent") is not False
            or receipt.get("database_write") is not False):
        raise ValueError("untrusted research review receipt")
    # This is a separate review packet, not a rewritten CRM or JEV result.
    return {
        "schema_version": "empire.jev.research_review_attachment.v1",
        "decision_fingerprint": digest,
        "jev_recommendation_unchanged": decision["action"],
        "jev_blockers_unchanged": list(decision["blockers"]),
        "research_status": receipt.get("status"),
        "reviewable_public_sources": receipt.get("inspected_source_count", 0),
        "original_provider_authentication_verified": False,
        "buyer_intent_verified": False,
        "contact_clearance_verified": False,
        "founder_review_required": True,
        "source_observations_not_proven_commercial_signals": True,
        "outbound_authorized": False, "database_write": False,
        "execution_authority": "none",
    }
