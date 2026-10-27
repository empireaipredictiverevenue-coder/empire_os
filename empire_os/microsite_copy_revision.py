"""Bounded draft copy revision: SlopMonster + fact-lock + deterministic diff.

The candidate is not published even when its heuristic score improves. The
existing SEO/site owner retains source, release, analytics and compliance authority.
"""
from __future__ import annotations

from copy import deepcopy
from difflib import unified_diff
import json
import re
from typing import Any, Mapping

from empire_os.predictive_microsite_factory import build_candidate, review_copy

FIELDS = ("headline", "subhead", "summary")
RISK_TERMS = re.compile(
    r"\b(?:guaranteed?|approved|certified|licensed|insured|trusted by|"
    r"available now|book today|verified buyers?|qualified leads?|"
    r"lowest price|best rated|five.star|award.winning|"
    r"no obligation|free quote|same.day|limited.time)\b", re.I)
NUMBERS = re.compile(r"\b\d[\d,.]*\b")
MARKUP = re.compile(r"<[^>]*>|https?://|\b(?:javascript:|data:)\b", re.I)


def _field_text(spec: Mapping[str, Any], key: str) -> str:
    value = spec.get(key)
    if not isinstance(value, str):
        raise ValueError(f"source {key} must be explicit; cannot revise inferred copy")
    return value


def review_copy_revision(
    original: Mapping[str, Any],
    proposed: Mapping[str, Any],
    *, model_label: str = "unverified_editorial_input",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Only three copy fields can change; all evidence remains byte-identical."""
    if not isinstance(proposed, Mapping) or set(proposed) != set(FIELDS):
        raise ValueError("revision must contain exactly headline/subhead/summary")
    source = {key: _field_text(original, key) for key in FIELDS}
    revised = {}
    blockers = []
    for field in FIELDS:
        text = proposed[field]
        if not isinstance(text, str) or not 15 <= len(text.strip()) <= 450:
            raise ValueError(f"revision {field} must be 15..450 characters")
        if MARKUP.search(text):
            blockers.append(f"{field}: markup/URLs are not permitted in revised prose")
        original_risk = {m.group(0).casefold() for m in RISK_TERMS.finditer(source[field])}
        added_risk = {m.group(0).casefold() for m in RISK_TERMS.finditer(text)} - original_risk
        if added_risk:
            blockers.append(f"{field}: new high-risk promotional claims must be evidenced")
        original_numbers = set(NUMBERS.findall(" ".join(source.values())))
        added_numbers = set(NUMBERS.findall(text)) - original_numbers
        if added_numbers:
            blockers.append(f"{field}: numerical claims added without supplied evidence")
        revised[field] = text.strip()
    if all(revised[key] == source[key] for key in FIELDS):
        blockers.append("no substantive copy changes proposed")
    new_spec = deepcopy(original)
    new_spec.update(revised)
    original_packet, original_html = build_candidate(original)
    proposed_packet, proposed_html = build_candidate(new_spec)
    original_score = original_packet["copy_audit"]["score"]
    proposed_score = proposed_packet["copy_audit"]["score"]
    if proposed_score < original_score:
        blockers.append("new SlopMonster category matches added")
    if proposed_packet["id"] != original_packet["id"]:
        blockers.append("source identity changed; prohibited")
    for key in ("market", "keyword", "content_evidence", "audience", "offer"):
        if proposed_packet[key] != original_packet[key]:
            blockers.append(f"immutable commercial/source field changed: {key}")
    diff = "\n".join(
        line for field in FIELDS for line in unified_diff(
            (source[field]+"\n").splitlines(), (revised[field]+"\n").splitlines(),
            fromfile=f"original_{field}", tofile=f"proposed_{field}", lineterm=""))
    review = {
        "schema_version": "empire.microsite_copy_revision_review.v1",
        "model_label": model_label[:90],
        "candidate_id": original_packet["id"],
        "original_score": original_score,
        "proposed_score": proposed_score,
        "changed_fields": [key for key in FIELDS if source[key] != revised[key]],
        "diff": diff[:4000],
        "status": "HOLD_CLAIM_OR_STYLE" if blockers else "DRAFT_EDITORIAL_REVIEW",
        "blockers": blockers,
        "original_source_evidence_preserved": True,
        "independent_factual_verification_complete": False,
        "independent_design_review_complete": False,
        "publication_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
    return review, new_spec


def offline_rewrite_instructions(spec: Mapping[str, Any]) -> dict[str, Any]:
    """No model calls. Structured JSON prompt for an approved local adapter."""
    original, _ = build_candidate(spec)
    source = {key: _field_text(spec, key) for key in FIELDS}
    return {
        "task": "rewrite_three_copy_fields_only",
        "model_input": {
            "market": original["market"]["area"],
            "keyword": original["keyword"]["record"]["keyword"],
            "audience": original["audience"],
            "offer": original["offer"],
            "source_copy": source,
        },
        "system_instruction": (
            "You edit a research website preview. Produce one JSON object with exactly "
            "headline, subhead, summary, all strings. Preserve meanings and conditions; "
            "improve specificity and reading flow, avoiding promotional AI cliches. "
            "No unsupported facts, numbers, claims of results, urgency, prices, "
            "testimonials, links, markup, guarantees or new services. "
            "No code fences or commentary."
        ),
        "local_model_only": True,
        "external_model_calls": 0,
        "auto_publish": False,
    }
