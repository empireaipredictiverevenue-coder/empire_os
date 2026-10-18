"""NewsJack-style public news intake → Empire JEV → organic traffic review.

No crawler, scheduler, hosted API, publishing, outbound, or new datastore.
Use source packets collected by the existing authorised research/Search owners.
A typed-decision provider is optional and MUST remain shadow-only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from ipaddress import ip_address
import json
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from empire_os.typed_decision_provider import (
    TypedDecisionProvider, TypedDecisionRequest,
)

SCHEMA = "empire.organic.newsjack_jev_review.v1"
DECISION_SCHEMA = "empire.organic.jev_news_relevance.v1"
LABELS = ("irrelevant", "research", "content_brief")
MAX_SIGNALS = 100
MAX_AGE_DAYS = 7
OWNED_HOSTS = frozenset({"empire-ai.co.uk", "www.empire-ai.co.uk"})


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _public_https(value: Any) -> str | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 1500:
        return None
    try:
        parsed = urlsplit(value.strip())
        host = parsed.hostname
        if (parsed.scheme.lower() != "https" or not host
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)
                or not all(c.isascii() and (c.isalnum() or c in ".-") for c in host)):
            return None
        try:
            if not ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host or host.endswith((".local", ".internal", ".test", ".invalid")):
                return None
        return urlunsplit(("https", host.lower(), parsed.path or "/", parsed.query, ""))
    except ValueError:
        return None


def _refs(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > 12:
        return ()
    if not all(isinstance(r, str) and 1 <= len(r.strip()) <= 220 for r in value):
        return ()
    return tuple(dict.fromkeys(r.strip() for r in value))


def _search_observation(value: Any, as_of: datetime) -> dict[str, Any] | None:
    """Accept only explicitly reader-attested GSC measurements, never predictions."""
    if not isinstance(value, Mapping):
        return None
    observed = _timestamp(value.get("observed_at"))
    impressions, clicks = value.get("impressions"), value.get("clicks")
    query, ref = value.get("query"), value.get("source_ref")
    if (value.get("source_kind") != "GSC"
            or value.get("trusted_reader_verified") is not True
            or not observed or not timedelta(0) <= as_of - observed <= timedelta(days=35)
            or type(impressions) is not int or type(clicks) is not int
            or not 0 <= clicks <= impressions
            or not isinstance(query, str) or not 2 <= len(query.strip()) <= 180
            or not isinstance(ref, str) or not 1 <= len(ref) <= 220):
        return None
    return {
        "source_kind": "GSC", "source_ref": ref, "query": query.strip(),
        "observed_at": observed.isoformat(), "impressions": impressions,
        "clicks": clicks,
        "scope": "historical_query_page_not_news_attribution"
        if value.get("metric_scope") == "historical_query_page_not_news_attribution"
        else "provided_reader_observation",
        "observation_window": value.get("observation_window")
        if isinstance(value.get("observation_window"), list) else None,
    }


def review_newsjack_jev_traffic(
    signals: Sequence[Mapping[str, Any]], *,
    as_of: str,
    approved_sectors: Sequence[str],
    approved_markets: Sequence[str],
    approved_destination_urls: Sequence[str] = (),
    provider: TypedDecisionProvider | None = None,
    confidence_threshold: float = 0.75,
) -> dict[str, Any]:
    """Rank bounded public signals for human traffic/content review only.

    Collection is delegated to the existing News/Research/Search Intelligence owners.
    Do not mistake a headline or JEV model confidence for traffic, lead or revenue proof.
    """
    clock = _timestamp(as_of)
    if clock is None:
        raise ValueError("timezone-aware as_of required")
    if (not isinstance(signals, (list, tuple))
            or len(signals) > MAX_SIGNALS
            or not all(isinstance(s, Mapping) for s in signals)):
        raise ValueError("bounded mapping signals required")
    if (not 0 <= confidence_threshold <= 1 or
            any(not isinstance(v, str) or not v.strip() for v in approved_sectors)
            or any(not isinstance(v, str) or not v.strip() for v in approved_markets)):
        raise ValueError("invalid review scope")
    sectors = {v.lower().strip() for v in approved_sectors}
    markets = {v.upper().strip() for v in approved_markets}
    destinations = {_public_https(v) for v in approved_destination_urls}
    if None in destinations or any(urlsplit(v).hostname not in OWNED_HOSTS for v in destinations if v):
        raise ValueError("destinations must be public HTTPS on an Empire AI owned host")
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for row in signals:
        signal_id, title = row.get("signal_id"), row.get("title")
        sector, market = row.get("sector"), row.get("market")
        url = _public_https(row.get("primary_source_url"))
        observed = _timestamp(row.get("observed_at"))
        published = _timestamp(row.get("published_at"))
        refs = _refs(row.get("evidence_refs"))
        blockers: list[str] = []
        if not isinstance(signal_id, str) or not 1 <= len(signal_id.strip()) <= 128:
            blockers.append("invalid_signal_id")
        if not isinstance(title, str) or not 8 <= len(title.strip()) <= 220:
            blockers.append("invalid_headline")
        if not isinstance(sector, str) or sector.lower().strip() not in sectors:
            blockers.append("unapproved_sector")
        if not isinstance(market, str) or market.upper().strip() not in markets:
            blockers.append("unapproved_market")
        if not url:
            blockers.append("invalid_public_source_url")
        if not refs:
            blockers.append("source_evidence_refs_missing")
        if not published or not observed:
            blockers.append("dated_source_observations_required")
        elif (published > observed or observed > clock
              or published > clock):
            blockers.append("future_or_inconsistent_timestamp")
        elif clock - published > timedelta(days=MAX_AGE_DAYS):
            blockers.append("stale_news_signal")
        if isinstance(signal_id, str):
            if signal_id in seen_ids:
                blockers.append("duplicate_signal_id")
            seen_ids.add(signal_id)
        if url:
            if url in seen_urls:
                blockers.append("duplicate_news_url")
            seen_urls.add(url)

        independent = row.get("independent_corroboration_verified") is True
        independent_refs = _refs(row.get("corroboration_evidence_refs"))
        # Two distinct citations without a checked independence assertion are
        # not considered independent; syndication frequently repeats one source.
        corroboration_verified = independent and bool(independent_refs)
        target = _public_https(row.get("destination_url"))
        destination_attested = (
            target is not None and target in destinations
            and row.get("destination_live_verified") is True
            and bool(_refs(row.get("destination_evidence_refs")))
        )
        search = _search_observation(row.get("search_observation"), clock)
        decision = None
        status = "HOLD_EVIDENCE" if blockers else "RESEARCH_REVIEW"
        missing = list(blockers)
        if not blockers:
            if not corroboration_verified:
                missing.append("independent_corroboration_required")
            if not destination_attested:
                missing.append("verified_live_destination_required")
            if search is None:
                missing.append("trusted_gsc_demand_observation_missing")
            if provider is None:
                missing.append("jev_shadow_decision_not_evaluated")
            else:
                # Source summary is supplied as untrusted data, not instructions.
                request = TypedDecisionRequest(
                    task_key="organic_news_relevance",
                    decision_schema_ref=DECISION_SCHEMA,
                    state_ref=f"news:{signal_id}",
                    state={
                        "headline": title.strip(), "sector": sector.lower().strip(),
                        "market": market.upper().strip(),
                        "primary_source_ref": refs[0],
                        "keyword": search["query"] if search else None,
                        "search_impressions": search["impressions"] if search else None,
                    },
                    allowed_labels=LABELS, risk_class="low",
                    instructions=(
                        "Classify editorial relevance for an approved market only; "
                        "do not infer real traffic, conversions, revenue, or source truth."
                    ),
                )
                try:
                    outcome = provider.evaluate(request)
                    outcome.validate(request)
                    if (outcome.shadow_only is not True
                            or outcome.execution_authority != "none"):
                        raise ValueError("provider_not_shadow_only")
                    decision = {
                        "label": outcome.label,
                        "confidence": outcome.confidence,
                        "provider_key": outcome.provider_key,
                        "model_key": outcome.model_key,
                        "source_ref": outcome.source_ref,
                        "scope": "classification_confidence_not_traffic_probability",
                    }
                    if outcome.confidence < confidence_threshold:
                        missing.append("low_confidence_shadow_decision")
                    elif outcome.label == "irrelevant":
                        status = "NOT_RELEVANT"
                    elif (outcome.label == "content_brief" and not missing):
                        status = "CONTENT_BRIEF_REVIEW"
                except (RuntimeError, ValueError, TypeError):
                    missing.append("jev_provider_unavailable_or_invalid")
        identity = json.dumps(
            {"id": signal_id, "url": url, "observed_at": row.get("observed_at"),
             "refs": refs}, sort_keys=True, default=str,
        )
        results.append({
            "signal_id": signal_id if isinstance(signal_id, str) else None,
            "title": title.strip() if isinstance(title, str) else None,
            "sector": sector.lower().strip() if isinstance(sector, str) else None,
            "market": market.upper().strip() if isinstance(market, str) else None,
            "primary_source_url": url,
            "published_at": published.isoformat() if published else None,
            "evidence_refs": list(refs),
            "status": status,
            "missing_evidence": missing,
            "corroboration_verified_by_input": corroboration_verified,
            "search_observation": search,
            "destination_url": target if destination_attested else None,
            "destination_operator_attested": destination_attested,
            "jev_shadow_decision": decision,
            "traffic_channels_for_review": (
                ["organic_search", "earned_media", "youtube", "linkedin", "newsletter"]
                if status in ("RESEARCH_REVIEW", "CONTENT_BRIEF_REVIEW") else []
            ),
            "content_brief_recommendation_only": status == "CONTENT_BRIEF_REVIEW",
            "actual_visitors": None,
            "actual_enquiries": None,
            "actual_revenue": False,
            "publishing_enabled": False,
            "outbound_enabled": False,
            "paid_media_spend_enabled": False,
            "execution_authority": "none",
            "evidence_fingerprint": sha256(identity.encode()).hexdigest(),
        })
    priority = {"CONTENT_BRIEF_REVIEW": 0, "RESEARCH_REVIEW": 1,
                "NOT_RELEVANT": 2, "HOLD_EVIDENCE": 3}
    results.sort(key=lambda v: (priority[v["status"]], v["signal_id"] or ""))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "candidate_count": len(results),
        "status_counts": dict(sorted(Counter(x["status"] for x in results).items())),
        "candidates": results,
        "source_collector": "existing_authorised_news_and_research_owner",
        "jev_provider_active": provider is not None,
        "newsjack_installed_or_invoked": False,
        "gsc_queried": False,
        "publishing_enabled": False,
        "outbound_enabled": False,
        "payment_enabled": False,
        "execution_authority": "none",
    }
