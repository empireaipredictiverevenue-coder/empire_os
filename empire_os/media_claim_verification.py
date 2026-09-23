"""Evidence-gated claim verification for Empire Media OS.

This module reuses:
- Media Research Pack for source/freshness lineage;
- Empire Search Fabric site_probe for bounded public-source observation;
- LLM Gateway / Model Router for proposal and entailment reasoning.

A search snippet can suggest a claim but can never verify itself. A factual claim
is promoted only when:
1. its cited source exists in the research pack;
2. the source is directly observed;
3. the proposed supporting quote is literally present in observed source text;
4. a bounded verification pass judges the quote to support the claim.

All failures are fail-closed. No public publishing or external mutation occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from empire_os.llm_gateway import LLMGateway
from empire_os.media_research_pack import (
    FRESHNESS_WINDOWS_DAYS,
    MediaResearchClaim,
)
from empire_os.search_fabric.site_probe import probe_site


INPUT = Path("runtime/media_os/input/research_pack_candidates.json")
OUTPUT = Path("runtime/media_os/claim_verification_latest.json")
VERIFIED_OUTPUT = Path(
    "runtime/media_os/input/verified_research_packs.json"
)

ProbeFn = Callable[..., Mapping[str, Any]]
ResolverFn = Callable[..., Any]

VERDICTS = frozenset({
    "SUPPORTED",
    "CONTESTED",
    "UNSUPPORTED",
    "UNKNOWN",
})


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            dict(row)
            for row in value
            if isinstance(row, Mapping)
        ]
    if isinstance(value, Mapping):
        for key in ("candidates", "items", "records"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [
                    dict(row)
                    for row in rows
                    if isinstance(row, Mapping)
                ]
    return []


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise_for_match(value: str) -> str:
    value = str(value or "")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().casefold()


def _quote_in_text(quote: str, visible_text: str) -> bool:
    needle = _normalise_for_match(quote)
    haystack = _normalise_for_match(visible_text)
    return bool(needle and len(needle) >= 12 and needle in haystack)


def _public_source_url_allowed(
    url: str,
    *,
    resolver: ResolverFn = socket.getaddrinfo,
) -> tuple[bool, str | None]:
    """Fail closed for localhost/private/link-local source URLs."""
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError:
        return False, "invalid_url"

    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported_scheme"
    if not parsed.hostname:
        return False, "hostname_missing"
    if parsed.username or parsed.password:
        return False, "userinfo_not_allowed"

    try:
        port = parsed.port
    except ValueError:
        return False, "invalid_port"
    if port not in {None, 80, 443}:
        return False, "nonstandard_port_not_allowed"

    host = parsed.hostname.strip().lower().rstrip(".")
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
    ):
        return False, "local_hostname_not_allowed"

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        return (
            (True, None)
            if literal.is_global
            else (False, "nonpublic_ip_not_allowed")
        )

    try:
        answers = resolver(
            host,
            port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except (OSError, socket.gaierror):
        return False, "dns_resolution_failed"

    addresses = []
    for answer in answers:
        try:
            address = answer[4][0]
            ip = ipaddress.ip_address(address)
        except (IndexError, TypeError, ValueError):
            continue
        addresses.append(ip)

    if not addresses:
        return False, "dns_no_ip_addresses"
    if any(not address.is_global for address in addresses):
        return False, "dns_resolved_nonpublic_ip"

    return True, None


def _source_catalog(pack: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in pack.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        ref = _clean(raw.get("source_ref"))
        if ref:
            output[ref] = dict(raw)
    return output


def observe_research_sources(
    pack: Mapping[str, Any],
    *,
    probe: ProbeFn = probe_site,
    max_sources: int = 5,
    request_timeout_seconds: float = 7.0,
    per_source_time_budget_seconds: float = 10.0,
    resolver: ResolverFn = socket.getaddrinfo,
) -> dict[str, Any]:
    """Directly observe bounded source text for later claim verification."""
    sources = _source_catalog(pack)
    selected = list(sources.items())[: max(1, min(int(max_sources), 8))]
    observations = []
    failures = []

    for source_ref, source in selected:
        url = _clean(source.get("lineage_ref"))
        allowed, rejection_reason = _public_source_url_allowed(
            url,
            resolver=resolver,
        )
        if not allowed:
            failures.append({
                "source_ref": source_ref,
                "reason": (
                    rejection_reason
                    or "no_observable_public_url"
                ),
            })
            continue

        try:
            probe_result = probe(
                url,
                max_pages=1,
                request_timeout=max(
                    1.0,
                    min(float(request_timeout_seconds), 15.0),
                ),
                time_budget_seconds=max(
                    2.0,
                    min(float(per_source_time_budget_seconds), 20.0),
                ),
                page_priority="default",
                public_only=True,
            )
        except Exception as exc:
            failures.append({
                "source_ref": source_ref,
                "reason": f"probe_error:{type(exc).__name__}",
            })
            continue

        if not isinstance(probe_result, Mapping) or (
            probe_result.get("ok") is not True
        ):
            failures.append({
                "source_ref": source_ref,
                "reason": _clean(
                    (probe_result or {}).get("error")
                ) or "source_observation_unavailable",
            })
            continue

        pages = [
            row
            for row in (probe_result.get("pages_checked") or [])
            if isinstance(row, Mapping)
        ]
        visible = "\n".join(
            _clean(row.get("visible_text"))
            for row in pages
            if _clean(row.get("visible_text"))
        )
        if not visible:
            failures.append({
                "source_ref": source_ref,
                "reason": "visible_text_unavailable",
            })
            continue

        observations.append({
            "source_ref": source_ref,
            "lineage_ref": url,
            "observed_url": (
                _clean(probe_result.get("final_url")) or url
            ),
            "observed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "visible_text": visible[:20_000],
            "visible_text_sha256": hashlib.sha256(
                visible.encode("utf-8")
            ).hexdigest(),
            "observation_method": "empire_search_fabric_site_probe",
            "direct_source_observed": True,
        })

    return {
        "schema_version": "empire.media.source_observation.v1",
        "research_id": pack.get("research_id"),
        "source_count": len(sources),
        "attempted_source_count": len(selected),
        "observed_source_count": len(observations),
        "failure_count": len(failures),
        "observations": observations,
        "failures": failures,
        "external_action": "read_only_public_observation",
        "external_write_performed": False,
        "execution_authority": "none",
    }


def _proposal_prompt(
    pack: Mapping[str, Any],
    observations: Mapping[str, Any],
    *,
    max_claims: int,
) -> tuple[str, list[dict[str, str]]]:
    source_rows = []
    observed_by_ref = {
        _clean(row.get("source_ref")): row
        for row in observations.get("observations") or []
        if isinstance(row, Mapping)
    }

    for raw in pack.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        ref = _clean(raw.get("source_ref"))
        observed = observed_by_ref.get(ref)
        if not observed:
            continue
        source_rows.append({
            "source_ref": ref,
            "url": raw.get("lineage_ref"),
            "observed_at": observed.get("observed_at"),
            "visible_text": str(
                observed.get("visible_text") or ""
            )[:12_000],
        })

    system = (
        "You are the Empire Media OS claim-proposal stage. "
        "Propose only narrow factual claims explicitly supported by the "
        "provided directly observed source text. Never infer demand, buyer "
        "intent, causation, market share, financial results, or revenue. "
        "Every proposed claim must cite exactly one or more source_ref values "
        "and include one short exact support_quote copied verbatim from one "
        "cited source. Return JSON only."
    )
    messages = [{
        "role": "user",
        "content": json.dumps({
            "task": "propose_evidence_bounded_media_claims",
            "research_id": pack.get("research_id"),
            "topic": pack.get("topic"),
            "thesis": pack.get("thesis"),
            "uncertainty": pack.get("uncertainty") or [],
            "max_claims": max_claims,
            "sources": source_rows,
            "required_output": {
                "claims": [{
                    "claim_id": "stable short identifier",
                    "text": "narrow factual claim",
                    "evidence_refs": ["source_ref"],
                    "support_source_ref": "source_ref",
                    "support_quote": "exact quote from visible_text",
                    "freshness_class": "CURRENT",
                    "uncertainty": "optional",
                }]
            },
        }),
    }]
    return system, messages


def propose_claims(
    pack: Mapping[str, Any],
    observations: Mapping[str, Any],
    *,
    gateway: LLMGateway,
    max_claims: int = 4,
) -> dict[str, Any]:
    bounded = max(1, min(int(max_claims), 6))
    if int(observations.get("observed_source_count") or 0) <= 0:
        return {
            "claims": [],
            "model_call_performed": False,
            "reason": "no_direct_source_observations",
        }

    system, messages = _proposal_prompt(
        pack,
        observations,
        max_claims=bounded,
    )
    try:
        result = gateway.structured_chat(
            messages,
            task="research",
            system=system,
            temperature=0.0,
            stakes="normal",
        )
    except Exception as exc:
        return {
            "claims": [],
            "model_call_performed": True,
            "reason": f"proposal_gateway_error:{type(exc).__name__}",
        }

    if not isinstance(result, Mapping):
        return {
            "claims": [],
            "model_call_performed": True,
            "reason": "proposal_response_not_object",
        }

    source_refs = set(_source_catalog(pack))
    observed_by_ref = {
        _clean(row.get("source_ref")): row
        for row in observations.get("observations") or []
        if isinstance(row, Mapping)
    }

    claims = []
    rejected = []
    for index, raw in enumerate(_records({"items": result.get("claims")})):
        claim_id = _clean(raw.get("claim_id")) or f"claim-{index + 1}"
        text = _clean(raw.get("text"))
        evidence_refs = [
            _clean(value)
            for value in (raw.get("evidence_refs") or [])
            if _clean(value)
        ]
        support_ref = _clean(raw.get("support_source_ref"))
        quote = _clean(raw.get("support_quote"))
        freshness = (
            _clean(raw.get("freshness_class")).upper()
            or "CURRENT"
        )

        problems = []
        if not text:
            problems.append("claim_text_missing")
        if not evidence_refs:
            problems.append("evidence_refs_missing")
        if any(ref not in source_refs for ref in evidence_refs):
            problems.append("unknown_evidence_ref")
        if support_ref not in evidence_refs:
            problems.append("support_ref_not_cited")
        observed = observed_by_ref.get(support_ref)
        if not observed:
            problems.append("support_source_not_directly_observed")
        elif not _quote_in_text(
            quote,
            str(observed.get("visible_text") or ""),
        ):
            problems.append("support_quote_not_found_in_source_text")
        if freshness not in FRESHNESS_WINDOWS_DAYS:
            problems.append("unsupported_freshness_class")

        if problems:
            rejected.append({
                "claim_id": claim_id,
                "problems": problems,
            })
            continue

        claims.append({
            "claim_id": claim_id,
            "text": text,
            "evidence_refs": list(dict.fromkeys(evidence_refs)),
            "support_source_ref": support_ref,
            "support_quote": quote,
            "freshness_class": freshness,
            "uncertainty": (
                _clean(raw.get("uncertainty")) or None
            ),
            "proposal_state": "PROPOSED_NOT_VERIFIED",
            "support_quote_machine_matched": True,
        })
        if len(claims) >= bounded:
            break

    return {
        "claims": claims,
        "rejected": rejected,
        "model_call_performed": True,
        "proposal_count": len(claims),
    }


def _verification_prompt(
    proposals: Iterable[Mapping[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    rows = []
    for raw in proposals:
        rows.append({
            "claim_id": raw.get("claim_id"),
            "claim": raw.get("text"),
            "support_quote": raw.get("support_quote"),
            "support_source_ref": raw.get("support_source_ref"),
        })

    system = (
        "You are the Empire Media OS evidence verifier. Judge only whether "
        "the exact support_quote logically supports the proposed claim. "
        "Do not use outside knowledge. If the claim is broader, stronger, "
        "more causal, more current, or more commercial than the quote, mark "
        "it UNSUPPORTED or UNKNOWN. Return JSON only."
    )
    messages = [{
        "role": "user",
        "content": json.dumps({
            "task": "claim_entailment_review",
            "claims": rows,
            "allowed_verdicts": sorted(VERDICTS),
            "required_output": {
                "reviews": [{
                    "claim_id": "claim id",
                    "verdict": "SUPPORTED|CONTESTED|UNSUPPORTED|UNKNOWN",
                    "confidence": 0.0,
                    "reason": "short explanation",
                }]
            },
        }),
    }]
    return system, messages


def verify_claims(
    proposals: Iterable[Mapping[str, Any]],
    *,
    gateway: LLMGateway,
) -> dict[str, Any]:
    proposal_rows = [dict(row) for row in proposals]
    if not proposal_rows:
        return {
            "reviews": [],
            "model_call_performed": False,
            "supported_count": 0,
        }

    system, messages = _verification_prompt(proposal_rows)
    try:
        result = gateway.structured_chat(
            messages,
            task="verification",
            system=system,
            temperature=0.0,
            stakes="high",
        )
    except Exception as exc:
        return {
            "reviews": [
                {
                    "claim_id": row.get("claim_id"),
                    "verdict": "UNKNOWN",
                    "confidence": None,
                    "reason": (
                        f"verification_gateway_error:"
                        f"{type(exc).__name__}"
                    ),
                }
                for row in proposal_rows
            ],
            "model_call_performed": True,
            "supported_count": 0,
        }

    review_by_id = {}
    if isinstance(result, Mapping):
        for raw in _records({"items": result.get("reviews")}):
            claim_id = _clean(raw.get("claim_id"))
            verdict = _clean(raw.get("verdict")).upper()
            if not claim_id or verdict not in VERDICTS:
                continue
            try:
                confidence = float(raw.get("confidence"))
            except (TypeError, ValueError):
                confidence = None
            if confidence is not None:
                confidence = max(0.0, min(1.0, confidence))
            review_by_id[claim_id] = {
                "claim_id": claim_id,
                "verdict": verdict,
                "confidence": confidence,
                "reason": _clean(raw.get("reason")) or None,
            }

    reviews = []
    for proposal in proposal_rows:
        claim_id = _clean(proposal.get("claim_id"))
        review = review_by_id.get(claim_id) or {
            "claim_id": claim_id,
            "verdict": "UNKNOWN",
            "confidence": None,
            "reason": "no_valid_verification_result",
        }
        # High-stakes factual promotion requires strong verifier confidence.
        if (
            review["verdict"] == "SUPPORTED"
            and (
                review["confidence"] is None
                or review["confidence"] < 0.80
            )
        ):
            review = {
                **review,
                "verdict": "UNKNOWN",
                "reason": "supported_but_confidence_below_0_80",
            }
        reviews.append(review)

    return {
        "reviews": reviews,
        "model_call_performed": True,
        "supported_count": sum(
            row["verdict"] == "SUPPORTED"
            for row in reviews
        ),
    }


def materialize_verified_pack(
    pack: Mapping[str, Any],
    *,
    proposals: Iterable[Mapping[str, Any]],
    reviews: Iterable[Mapping[str, Any]],
    source_observations: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    proposal_by_id = {
        _clean(row.get("claim_id")): dict(row)
        for row in proposals
        if _clean(row.get("claim_id"))
    }
    review_by_id = {
        _clean(row.get("claim_id")): dict(row)
        for row in reviews
        if _clean(row.get("claim_id"))
    }
    observed_by_ref = {
        _clean(row.get("source_ref")): dict(row)
        for row in source_observations.get("observations") or []
        if isinstance(row, Mapping)
    }

    claim_rows = []
    contested = []
    unsupported = []
    unknown = []

    for claim_id, proposal in proposal_by_id.items():
        review = review_by_id.get(claim_id) or {
            "verdict": "UNKNOWN",
            "confidence": None,
            "reason": "missing_review",
        }
        verdict = _clean(review.get("verdict")).upper()
        if verdict == "SUPPORTED":
            support_ref = _clean(proposal.get("support_source_ref"))
            observed = observed_by_ref.get(support_ref) or {}
            claim = MediaResearchClaim(
                claim_id=claim_id,
                text=_clean(proposal.get("text")),
                evidence_refs=tuple(
                    _clean(value)
                    for value in (
                        proposal.get("evidence_refs") or []
                    )
                    if _clean(value)
                ),
                freshness_class=(
                    _clean(
                        proposal.get("freshness_class")
                    ).upper()
                    or "CURRENT"
                ),
                source_timestamp=(
                    _clean(observed.get("observed_at")) or None
                ),
                uncertainty=(
                    _clean(proposal.get("uncertainty")) or None
                ),
            ).as_dict(now=now)
            claim["verification"] = {
                "verdict": "SUPPORTED",
                "confidence": review.get("confidence"),
                "reason": review.get("reason"),
                "support_source_ref": support_ref,
                "support_quote": proposal.get("support_quote"),
                "direct_source_observed": True,
                "support_quote_machine_matched": True,
                "verification_method": (
                    "direct_source_quote_plus_llm_entailment"
                ),
            }
            claim_rows.append(claim)
        elif verdict == "CONTESTED":
            contested.append({
                "claim_id": claim_id,
                "text": proposal.get("text"),
                "review": review,
            })
        elif verdict == "UNSUPPORTED":
            unsupported.append({
                "claim_id": claim_id,
                "text": proposal.get("text"),
                "review": review,
            })
        else:
            unknown.append({
                "claim_id": claim_id,
                "text": proposal.get("text"),
                "review": review,
            })

    stale = [
        row["claim_id"]
        for row in claim_rows
        if row.get("stale") is True
    ]
    script_ready = (
        bool(claim_rows)
        and not stale
        and not unknown
    )

    return {
        **dict(pack),
        "schema_version": "empire.media.verified_research_pack.v1",
        "claims": claim_rows,
        "verified_claim_count": len(claim_rows),
        "contested_claims": contested,
        "unsupported_claims": unsupported,
        "unknown_claims": unknown,
        "stale_claim_ids": stale,
        "claim_verification_required": not script_ready,
        "claim_verification_complete": not unknown,
        "script_ready": script_ready,
        "source_observations": dict(source_observations),
        "source_observations_are_verified_facts": False,
        "automatic_script_generation_authorized": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_claim_verification_queue(
    research_packs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = []
    for raw in research_packs:
        pack = dict(raw)
        if pack.get("script_ready") is True:
            continue
        rows.append({
            "research_id": pack.get("research_id"),
            "topic": pack.get("topic"),
            "source_count": len(pack.get("sources") or []),
            "source_observation_count": int(
                pack.get("source_observation_count") or 0
            ),
            "claim_verification_required": True,
        })
    return {
        "schema_version": "empire.media.claim_verification_queue.v1",
        "candidate_count": len(rows),
        "candidates": rows,
        "automatic_public_action": False,
        "execution_authority": "none",
    }


def refresh_media_claim_verification(
    repo_root: Path,
    *,
    gateway: LLMGateway | None = None,
    probe: ProbeFn = probe_site,
    max_packs: int = 2,
    max_claims_per_pack: int = 4,
    max_sources_per_pack: int = 3,
    source_request_timeout_seconds: float = 6.0,
    source_time_budget_seconds: float = 8.0,
    force: bool = False,
    resolver: ResolverFn = socket.getaddrinfo,
) -> dict[str, Any]:
    source = _read_json(repo_root / INPUT)
    packs = _records(source)
    pack_by_id = {
        _clean(row.get("research_id")): row
        for row in packs
        if _clean(row.get("research_id"))
    }
    pack_fingerprints = {
        research_id: _fingerprint(pack)
        for research_id, pack in pack_by_id.items()
    }
    input_fingerprint = _fingerprint(packs)

    previous_verified_payload = _read_json(
        repo_root / VERIFIED_OUTPUT
    )
    previous_verified = {
        _clean(row.get("research_id")): row
        for row in _records(previous_verified_payload)
        if _clean(row.get("research_id"))
    }

    pending: list[dict[str, Any]] = []
    preserved: dict[str, dict[str, Any]] = {}
    for research_id, pack in pack_by_id.items():
        prior = previous_verified.get(research_id)
        unchanged = (
            isinstance(prior, Mapping)
            and prior.get("source_input_fingerprint")
            == pack_fingerprints[research_id]
            and prior.get("verification_retry_required") is not True
        )
        if unchanged and not force:
            preserved[research_id] = dict(prior)
        else:
            pending.append(pack)

    limit = max(1, min(int(max_packs), 5))
    selected = pending[:limit]

    llm = gateway or (LLMGateway() if selected else None)
    results = []
    processed: dict[str, dict[str, Any]] = {}

    for pack in selected:
        research_id = _clean(pack.get("research_id"))
        observations = observe_research_sources(
            pack,
            probe=probe,
            max_sources=max_sources_per_pack,
            request_timeout_seconds=source_request_timeout_seconds,
            per_source_time_budget_seconds=source_time_budget_seconds,
            resolver=resolver,
        )
        proposals = propose_claims(
            pack,
            observations,
            gateway=llm,
            max_claims=max_claims_per_pack,
        )
        verification = verify_claims(
            proposals.get("claims") or [],
            gateway=llm,
        )
        verified = materialize_verified_pack(
            pack,
            proposals=proposals.get("claims") or [],
            reviews=verification.get("reviews") or [],
            source_observations=observations,
        )
        verified["source_input_fingerprint"] = (
            pack_fingerprints[research_id]
        )
        verified["verification_attempted_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        verified["verification_attempt_complete"] = True
        proposal_reason = _clean(proposals.get("reason"))
        source_failures = observations.get("failures") or []
        verifier_unknown = bool(verified.get("unknown_claims"))
        transient_proposal_failure = (
            "gateway_error" in proposal_reason
            or proposal_reason in {
                "no_direct_source_observations",
                "proposal_response_not_object",
            }
        )
        verified["verification_retry_required"] = bool(
            verifier_unknown
            or transient_proposal_failure
            or (
                not observations.get("observed_source_count")
                and source_failures
            )
        )
        processed[research_id] = verified

        results.append({
            "research_id": research_id,
            "topic": pack.get("topic"),
            "observed_source_count": observations.get(
                "observed_source_count"
            ),
            "proposal_count": proposals.get("proposal_count", 0),
            "supported_count": verification.get(
                "supported_count", 0
            ),
            "verified_claim_count": verified[
                "verified_claim_count"
            ],
            "script_ready": verified["script_ready"],
            "proposal_rejections": proposals.get("rejected") or [],
            "source_failures": observations.get("failures") or [],
        })

    current_verified: list[dict[str, Any]] = []
    for research_id in pack_by_id:
        row = processed.get(research_id) or preserved.get(research_id)
        if row is not None:
            current_verified.append(row)

    generated_at = datetime.now(timezone.utc).isoformat()
    remaining = max(0, len(pending) - len(selected))
    payload = {
        "schema_version": "empire.media.claim_verification_runtime.v2",
        "mode": "OBSERVE",
        "generated_at": generated_at,
        "ok": True,
        "input_fingerprint": input_fingerprint,
        "research_pack_count": len(packs),
        "already_current_pack_count": len(preserved),
        "pending_pack_count_before_run": len(pending),
        "processed_pack_count": len(selected),
        "remaining_pack_count": remaining,
        "limits": {
            "max_packs": limit,
            "max_claims_per_pack": max(
                1, min(int(max_claims_per_pack), 6)
            ),
            "max_sources_per_pack": max(
                1, min(int(max_sources_per_pack), 8)
            ),
            "source_request_timeout_seconds": max(
                1.0,
                min(float(source_request_timeout_seconds), 15.0),
            ),
            "source_time_budget_seconds": max(
                2.0,
                min(float(source_time_budget_seconds), 20.0),
            ),
        },
        "verified_pack_count": len(current_verified),
        "verified_claim_count": sum(
            int(row.get("verified_claim_count") or 0)
            for row in current_verified
        ),
        "script_ready_count": sum(
            row.get("script_ready") is True
            for row in current_verified
        ),
        "results": results,
        "skipped_unchanged": not selected and not force,
        "external_reads_performed": any(
            int(row.get("observed_source_count") or 0) > 0
            for row in results
        ),
        "external_write_performed": False,
        "database_write_performed": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    _write_json(repo_root / OUTPUT, payload)
    _write_json(
        repo_root / VERIFIED_OUTPUT,
        {
            "schema_version": "empire.media.verified_research_packs.v2",
            "generated_at": generated_at,
            "candidate_count": len(current_verified),
            "verified_claim_count": payload["verified_claim_count"],
            "script_ready_count": payload["script_ready_count"],
            "remaining_pack_count": remaining,
            "candidates": current_verified,
            "public_publish_authorized": False,
            "execution_authority": "none",
        },
    )
    return payload
