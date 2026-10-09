"""Automatic, bounded OKF research discovery for scoped Astra evidence tasks.

Retrieval provides neutral source hints only. It cannot enqueue, approve,
change work identity, generate instructions, or influence execution authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from empire_os.okf_adapter import list_private_research

MAX_BUNDLES = 128
MAX_BUNDLE_AGE_HOURS = 48
MAX_MATCHES = 5
RUN_NAME = re.compile(r"run-(\d{8}T\d{6}\.\d{6}Z)\Z")
DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,251})[a-z0-9]\Z")
RESEARCH_TASKS = {
    "identity_enrichment": {"verify_decision_maker", "enrich_identity", "research_more"},
    "buyer_review": {"prepare_buyer_review", "research_more"},
    "buyer_capacity_readiness": {"inspect_evidence", "research_more"},
    "search_fabric": {"inspect_evidence", "research_more"},
    "intelligence_fabric": {"inspect_evidence", "research_more"},
}


def _exact_domain(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 400:
        return ""
    raw = value.strip().lower()
    if "://" in raw:
        try:
            url = urlsplit(raw)
            if (
                url.scheme not in {"http", "https"}
                or url.username or url.password or url.port not in (None, 80, 443)
                or url.query or url.fragment
            ):
                return ""
            raw = url.hostname or ""
        except ValueError:
            return ""
    if "/" in raw or "@" in raw or ":" in raw:
        return ""
    host = raw.rstrip(".").removeprefix("www.")
    if (
        not DOMAIN.fullmatch(host) or ".." in host
        or host.startswith(".") or "." not in host
    ):
        return ""
    return host


def _task_domain(step: Mapping[str, Any]) -> str:
    # Explicit structured identity only. No matching on natural-language
    # prompt content, opportunity snippets, titles, or evidence text.
    if (
        step.get("auto_dispatch_eligible") is not True
        or step.get("founder_gate_required") is True
        or step.get("authority") not in {"observe", "internal_write"}
        or str(step.get("action") or "") not in RESEARCH_TASKS.get(
            str(step.get("target_component") or ""), set()
        )
    ):
        return ""
    seen: set[str] = set()
    for field in ("intelligence_request", "memory_query"):
        metadata = step.get(field)
        if not isinstance(metadata, Mapping):
            continue
        for key in ("company_domain", "buyer_domain", "company_website", "website"):
            if key in metadata:
                value = _exact_domain(metadata.get(key))
                if not value:
                    return ""
                seen.add(value)
    return next(iter(seen)) if len(seen) == 1 else ""


def _latest_bundle(root: Path, now: datetime) -> tuple[Path | None, str]:
    folder = root / "runtime/knowledge/okf_private"
    if folder.is_symlink() or not folder.is_dir():
        return None, "private_bundle_missing"
    eligible: list[tuple[datetime, Path]] = []
    children = list(folder.iterdir())
    if len(children) > MAX_BUNDLES:
        return None, "bundle_inventory_limit"
    for child in children:
        match = RUN_NAME.fullmatch(child.name)
        if not match or child.is_symlink() or not child.is_dir():
            continue
        try:
            recorded = datetime.strptime(
                match.group(1), "%Y%m%dT%H%M%S.%fZ",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        eligible.append((recorded, child))
    if not eligible:
        return None, "private_bundle_missing"
    latest_time, latest = max(eligible, key=lambda entry: entry[0])
    age = now - latest_time
    if age > timedelta(hours=MAX_BUNDLE_AGE_HOURS) or age < -timedelta(minutes=5):
        return None, "bundle_too_old_or_future_dated"
    return latest, "available"


def auto_retrieve_for_astra(
    repo_root: str | Path,
    admitted_steps: list[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve same-company, fresh source hints for explicitly eligible tasks."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("aware_clock_required")
    current = current.astimezone(timezone.utc)
    matches = []
    for step in admitted_steps[:30]:
        if not isinstance(step, Mapping):
            continue
        domain = _task_domain(step)
        if domain:
            matches.append((str(step.get("step_id") or ""), domain))
    base = {
        "mode": "OBSERVE",
        "research_only": True,
        "trust": "unverified",
        "execution_authority": "none",
        "queue_mutated": False,
        "outbound_authorized": False,
        "matched_task_count": 0,
        "results": [],
    }
    if not matches:
        return {**base, "status": "no_relevant_company_bound_task"}
    bundle, status = _latest_bundle(Path(repo_root).resolve(), current)
    if bundle is None:
        return {**base, "status": status}
    try:
        research = list_private_research(bundle, now=current, max_results=30)
        if research.get("execution_authority") != "none":
            raise ValueError("untrusted_research_authority")
        index = {
            str(row.get("concept_id") or "").removeprefix("buyers/"): row
            for row in (research.get("results") or [])
            if isinstance(row, Mapping)
        }
        included: set[tuple[str, str]] = set()
        for step_id, domain in matches:
            row = index.get(domain)
            if not isinstance(row, Mapping):
                continue
            if (
                row.get("fresh") is not True
                or row.get("trust") != "unverified"
                or row.get("execution_authority") != "none"
                or not row.get("sources")
            ):
                continue
            key = (step_id, domain)
            if key in included:
                continue
            included.add(key)
            base["results"].append({
                "step_id": step_id,
                "concept_id": f"buyers/{domain}",
                "source_urls": list(row["sources"])[:3],
                "observed_relationship": str(row.get("relationship") or "unknown"),
                "fresh": True,
                "trust": "unverified",
                "execution_authority": "none",
            })
            if len(base["results"]) >= MAX_MATCHES:
                break
        base["matched_task_count"] = len(included)
        return {
            **base,
            "status": "matched" if included else "no_current_relevant_evidence",
            "bundle_id": bundle.name,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {**base, "status": "unavailable", "reason": type(exc).__name__}
