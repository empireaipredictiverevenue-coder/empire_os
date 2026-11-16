"""Connect existing last30days research and first-party GSC readers to Empire JEV.

Pure, bounded transformations; nothing crawls, publishes, emails or mutates DB.
Typed decision and original-source verification remain separate evidence owners.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from empire_os.jev_newsjack_traffic import _public_https, _timestamp, OWNED_HOSTS
from empire_os.search_intelligence.search_console import (
    GoogleSearchConsoleAdapter, SearchConsoleUnavailable,
)


def prepare_official_news_media_os_preview(
    review: Mapping[str, Any], *, as_of: str,
) -> dict[str, Any]:
    """Translate approved *research review* items into existing MediaOS packs.

    Only official primary references are accepted. This pure adapter creates
    an unsubmitted, unverified handoff for the existing MediaOS owner; it
    neither changes MediaOS input nor starts a scheduled NewsJack worker.
    """
    from empire_os.media_research_pack import (
        MediaResearchPack, MediaResearchSource,
    )

    stamp = _timestamp(as_of)
    if stamp is None:
        raise ValueError("timezone-aware handoff timestamp required")
    if (not isinstance(review, Mapping)
            or review.get("schema_version")
                != "empire.organic.newsjack_jev_review.v1"
            or review.get("mode") != "OBSERVE"
            or review.get("execution_authority") != "none"
            or review.get("publishing_enabled") is not False
            or review.get("outbound_enabled") is not False):
        raise ValueError("trusted read-only NewsJack review required")
    rows = review.get("candidates")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("bounded NewsJack candidates required")
    packs = []
    seen = set()
    held = 0
    for row in rows:
        if not isinstance(row, Mapping):
            held += 1
            continue
        if row.get("status") not in ("RESEARCH_REVIEW", "CONTENT_BRIEF_REVIEW"):
            held += 1
            continue
        signal_id = row.get("signal_id")
        title = row.get("title")
        sector = row.get("sector")
        market = row.get("market")
        url = _public_https(row.get("primary_source_url"))
        refs = row.get("evidence_refs")
        precision = row.get("publication_precision")
        host = urlsplit(url).hostname if url else None
        official = (
            host == "www.federalregister.gov"
            and any(
                isinstance(ref, str) and
                ref.startswith("federalregister:api:")
                for ref in (refs if isinstance(refs, list) else [])
            )
        ) or (
            host == "www.gov.uk"
            and any(
                isinstance(ref, str) and
                ref.startswith("govuk:content_api:")
                for ref in (refs if isinstance(refs, list) else [])
            )
        )
        if (not official
                or not isinstance(signal_id, str)
                or not 1 <= len(signal_id) <= 128
                or not isinstance(title, str) or not 8 <= len(title) <= 220
                or sector not in ("solar", "roofing", "hvac", "dental", "ai")
                or market not in ("GB", "US")
                or not isinstance(refs, list) or not refs
                or not all(isinstance(ref, str) and ref for ref in refs)
                or precision not in ("instant", "day")
                or row.get("actual_revenue") is not False
                or row.get("publishing_enabled") is not False
                or row.get("outbound_enabled") is not False
                or row.get("execution_authority") != "none"):
            held += 1
            continue
        # The JEV reviewer checked time/market scope; preserve day-only
        # publication precision. Never infer exact clock time or article truth.
        uid = signal_id + "|" + url
        if uid in seen:
            held += 1
            continue
        seen.add(uid)
        source_ref = refs[0]
        source = MediaResearchSource(
            source_ref=source_ref,
            source_type="official_news_metadata_reference",
            observed_at=stamp.isoformat(),
            lineage_ref=url,
            rights_state="RESEARCH_REFERENCE_ONLY",
        )
        stable = sha256(uid.encode()).hexdigest()[:16]
        research_id = "media-research:" + stable
        pack = MediaResearchPack(
            research_id=research_id,
            topic=f"{sector} / {market}: {title}",
            thesis=(
                "Review official-source evidence independently before "
                "drawing claims about this news development."
            ),
            audience=f"business operators in {market}",
            sources=(source,),
            claims=(),
            empire_data_refs=tuple(refs[:8]),
            uncertainty=(
                "Official metadata does not independently corroborate a headline.",
                "No buyer interest, traffic or revenue is inferred.",
                "Publication timing and commercial-use rights require review.",
            ),
            generated_at=stamp.isoformat(),
        ).as_dict()
        pack.update({
            "newsjack_signal_id": signal_id,
            "publication_date": row.get("publication_date"),
            "published_at": row.get("published_at"),
            "publication_precision": precision,
            "newsjack_review_status": row["status"],
            "opportunity_key": "newsjack:" + signal_id,
            "opportunity_class": "news_editorial_research",
            "source_observation_count": 1,
            "verified_claim_count": 0,
            "claim_verification_required": True,
            "script_ready": False,
            "source_observations_are_verified_facts": False,
            "automatic_script_generation_authorized": False,
            "public_publish_authorized": False,
            "actual_revenue": False,
            "execution_authority": "none",
        })
        packs.append(pack)

    return {
        "schema_version": "empire.organic.newsjack_media_os_preview.v1",
        "mode": "OBSERVE",
        "generated_at": stamp.isoformat(),
        "candidate_count": len(packs),
        "held_count": held,
        "research_packs": packs,
        "target_existing_owner": "media_os.research_intake",
        "media_os_queue_written": False,
        "newsjack_worker_started": False,
        "source_metadata_not_verified_claims": True,
        "verified_claim_count": 0,
        "script_ready_count": 0,
        "public_publish_authorized": False,
        "outbound_enabled": False,
        "payment_enabled": False,
        "execution_authority": "none",
    }


def reconcile_official_news_media_os_intake(
    current_media_research: Mapping[str, Any],
    newsjack_preview: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure, source-preserving intake preview; the MediaOS owner makes writes.

    The canonical MediaOS research bridge has changed since this specialist
    branch forked. Do not import or overwrite the old bridge source. This
    function accepts the current bridge's *produced JSON envelope* instead.
    """
    if (not isinstance(current_media_research, Mapping)
            or current_media_research.get("schema_version")
            != "empire.media.research_candidates.v1"
            or current_media_research.get("mode") != "OBSERVE"
            or current_media_research.get("public_publish_authorized") is not False
            or current_media_research.get("execution_authority") != "none"):
        raise ValueError("current owner MediaOS research snapshot required")
    original = current_media_research.get("candidates")
    if not isinstance(original, list) or len(original) > 100:
        raise ValueError("bounded existing MediaOS candidate list required")
    if (not isinstance(newsjack_preview, Mapping)
            or newsjack_preview.get("schema_version")
            != "empire.organic.newsjack_media_os_preview.v1"
            or newsjack_preview.get("mode") != "OBSERVE"
            or newsjack_preview.get("media_os_queue_written") is not False
            or newsjack_preview.get("verified_claim_count") != 0
            or newsjack_preview.get("public_publish_authorized") is not False
            or newsjack_preview.get("execution_authority") != "none"):
        raise ValueError("unsubmitted NewsJack research preview required")
    pending = newsjack_preview.get("research_packs")
    if not isinstance(pending, list) or len(pending) > 20:
        raise ValueError("bounded NewsJack research preview required")
    seen_ids, seen_urls = set(), set()
    for row in original:
        if (not isinstance(row, Mapping)
                or not isinstance(row.get("research_id"), str)
                or row.get("script_ready") is not False
                or row.get("public_publish_authorized") is not False
                or row.get("claims") != []):
            raise ValueError("existing candidate is not claimless research")
        rid = row["research_id"]
        if rid in seen_ids:
            raise ValueError("duplicate existing MediaOS research ID")
        seen_ids.add(rid)
        sources = row.get("sources")
        if not isinstance(sources, list) or len(sources) > 40:
            raise ValueError("unexpected existing MediaOS source shape")
        for source in sources:
            if not isinstance(source, Mapping):
                raise ValueError("unexpected existing source item")
            url = _public_https(source.get("lineage_ref"))
            if url:
                seen_urls.add(url)
    proposed, held = [], []
    for raw in pending:
        if not isinstance(raw, Mapping):
            held.append("invalid_preview_item")
            continue
        rid = raw.get("research_id")
        refs = raw.get("sources")
        source = refs[0] if isinstance(refs, list) and len(refs) == 1 else {}
        url = _public_https(source.get("lineage_ref")) if isinstance(source, Mapping) else None
        host = urlsplit(url).hostname if url else None
        sref = source.get("source_ref") if isinstance(source, Mapping) else None
        path = urlsplit(url).path if url else ""
        official = (
            host == "www.gov.uk"
            and path.startswith(("/guidance/", "/government/", "/statistics/"))
            and isinstance(sref, str)
            and sref.startswith("govuk:content_api:")
        ) or (
            host == "www.federalregister.gov"
            and path.startswith("/documents/")
            and isinstance(sref, str)
            and sref.startswith("federalregister:api:")
        )
        if (not official
                or not isinstance(rid, str) or not rid.startswith("media-research:")
                or raw.get("schema_version") != "empire.media.research_pack.v1"
                or raw.get("mode") != "OBSERVE"
                or raw.get("claims") != []
                or raw.get("script_ready") is not False
                or raw.get("claim_verification_required") is not True
                or raw.get("verified_claim_count") != 0
                or raw.get("source_observations_are_verified_facts") is not False
                or raw.get("automatic_script_generation_authorized") is not False
                or raw.get("actual_revenue") is not False
                or raw.get("public_publish_authorized") is not False
                or raw.get("execution_authority") != "none"
                or source.get("rights_state") != "RESEARCH_REFERENCE_ONLY"
                or source.get("source_type") != "official_news_metadata_reference"
                or raw.get("opportunity_class") != "news_editorial_research"):
            held.append("untrusted_or_unsupported_news_preview")
            continue
        if rid in seen_ids or url in seen_urls:
            held.append("already_present_in_existing_research")
            continue
        seen_ids.add(rid)
        seen_urls.add(url)
        proposed.append(dict(raw))
    digest = sha256(json.dumps(
        {"existing": original, "proposed": proposed},
        sort_keys=True, default=str, separators=(",", ":"),
    ).encode()).hexdigest()
    return {
        "schema_version": "empire.organic.newsjack_media_os_reconciliation.v1",
        "mode": "OBSERVE",
        "existing_candidate_count": len(original),
        "proposed_newsjack_candidate_count": len(pending),
        "new_research_candidate_count": len(proposed),
        "held_newsjack_candidate_count": len(held),
        "hold_reasons": held,
        "merged_preview_candidate_count": len(original) + len(proposed),
        "merged_preview_sha256": digest,
        "new_research_packs": proposed,
        "target_existing_owner": "media_os.research_bridge",
        "media_os_input_written": False,
        "source_research_is_not_factual_verification": True,
        "verified_claim_count": 0,
        "script_ready_count": 0,
        "public_publish_authorized": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }


def signals_from_last30days_agent_export(
    export: Mapping[str, Any], *, sector: str, market: str,
) -> dict[str, Any]:
    """Translate existing last30days agent-export v1.2 without promoting claims.

    Research-export stories are observations, not corroborated news facts.
    Date-only publication stamps remain unknown rather than inventing midnight.
    """
    if not isinstance(export, Mapping) or export.get("schema_version") != "1.2":
        raise ValueError("expected last30days agent-export v1.2")
    generated = _timestamp(export.get("generated_at"))
    results, status = export.get("results"), export.get("source_status")
    if (generated is None or not isinstance(results, list)
            or len(results) > 100 or not isinstance(status, Mapping)
            or not isinstance(sector, str) or not sector.strip()
            or not isinstance(market, str) or not market.strip()):
        raise ValueError("invalid bounded research export")
    mapped = []
    rejected = 0
    for entry in results:
        if not isinstance(entry, Mapping):
            rejected += 1
            continue
        source, key = entry.get("source"), entry.get("candidate_id")
        if (not isinstance(source, str) or source not in status
                or status[source] not in ("ok", "partial")
                or not isinstance(key, str) or not 1 <= len(key) <= 128):
            rejected += 1
            continue
        if not _public_https(entry.get("url")):
            rejected += 1
            continue
        published = _timestamp(entry.get("published_at"))
        # Source capture identity is an observation receipt, not independent
        # fact-checking or proof that the publisher made the headline claim.
        identity = json.dumps({
            "generated_at": generated.isoformat(), "candidate_id": key,
            "url": entry["url"], "source": source,
            "title": entry.get("title"), "published_at": entry.get("published_at"),
        }, sort_keys=True, default=str)
        ref = "last30days:agent_export:" + sha256(identity.encode()).hexdigest()
        mapped.append({
            "signal_id": "last30days:" + sha256(
                (source + ":" + key + ":" + str(entry["url"])).encode()
            ).hexdigest()[:24],
            "title": entry.get("title"),
            "sector": sector, "market": market,
            "primary_source_url": entry["url"],
            "published_at": published.isoformat() if published else None,
            "observed_at": generated.isoformat(),
            "evidence_refs": [ref],
            "source_adapter": "last30days_agent_export_1.2",
            "source_kind": source,
            "timestamp_granularity": (
                "timezone_aware_instant" if published else "unknown_or_date_only"
            ),
            "independent_corroboration_verified": False,
            "destination_live_verified": False,
        })
    return {
        "schema_version": "empire.organic.last30days_news_intake.v1",
        "mode": "OBSERVE", "signals": mapped, "mapped_count": len(mapped),
        "rejected_count": rejected, "generated_at": generated.isoformat(),
        "published_claims_verified": False, "automatic_publication": False,
        "execution_authority": "none",
    }


def signals_from_last30days_research_handoff(
    handoff: Mapping[str, Any], *, topic: str, sector: str, market: str,
    as_of: str,
) -> dict[str, Any]:
    """Consume the existing MediaOS handoff, never infer commercial evidence.

    Topic/sector/market are explicit operator research scope, not verified
    publisher geography. Topic labels are not article headlines. The original
    JEV reviewer still applies its stricter seven-day reactive-news window.
    """
    clock = _timestamp(as_of)
    generated = _timestamp(handoff.get("generated_at")) if isinstance(handoff, Mapping) else None
    flags = ("external_action_authorized", "public_publish_authorized",
             "database_write_authorized", "revenue_recognized",
             "buyer_intent_or_search_volume_from_engagement")
    if (clock is None or generated is None
            or not timedelta(0) <= clock - generated <= timedelta(hours=2)
            or handoff.get("schema_version") != "empire.last30days.research_handoff.v1"
            or handoff.get("mode") != "OBSERVE"
            or handoff.get("execution_authority") != "none"
            or any(handoff.get(key) is not False for key in flags)
            or not isinstance(topic, str) or not 1 <= len(topic) <= 110
            or not isinstance(sector, str) or not sector.strip()
            or market not in ("GB", "US")):
        raise ValueError("trusted fresh research handoff and explicit scope required")
    topics = handoff.get("topics")
    if (not isinstance(topics, list) or len(topics) > 4
            or type(handoff.get("topic_count")) is not int
            or handoff["topic_count"] != len(topics)):
        raise ValueError("bounded topic census required")
    total = 0
    selected = None
    names = set()
    for row in topics:
        if (not isinstance(row, Mapping) or not isinstance(row.get("topic"), str)
                or row["topic"] in names or not 1 <= len(row["topic"]) <= 110
                or row.get("review_status") != "REQUIRES_INDEPENDENT_TOPIC_RELEVANCE_AND_FACT_CHECK"
                or not isinstance(row.get("observations"), list)
                or len(row["observations"]) > 30
                or type(row.get("candidate_observation_count")) is not int
                or row["candidate_observation_count"] != len(row["observations"])):
            raise ValueError("research topic contract invalid")
        names.add(row["topic"])
        total += len(row["observations"])
        if row["topic"] == topic:
            selected = row
    if (type(handoff.get("source_observation_count")) is not int
            or handoff["source_observation_count"] != total or selected is None):
        raise ValueError("research source census or selected topic invalid")
    signals = []
    rejected = duplicates = 0
    seen_refs, seen_urls = set(), set()
    for entry in selected["observations"]:
        if not isinstance(entry, Mapping):
            rejected += 1
            continue
        ref, url = entry.get("source_ref"), _public_https(entry.get("source_url"))
        published = _timestamp(entry.get("published_at"))
        if (not isinstance(ref, str) or not ref.startswith("last30days:source:")
                or not 19 <= len(ref) <= 128 or url is None
                or published is None or published > generated
                or not timedelta(0) <= clock - published <= timedelta(days=30)
                or entry.get("source_type") not in ("reddit", "hackernews", "youtube", "github", "web")
                or entry.get("rights") != "PUBLIC_RESEARCH_REFERENCE_ONLY"
                or any(entry.get(key) is not False for key in (
                    "claim_verified", "buyer_intent_verified", "local_geography_verified",
                    "topic_relevance_verified", "source_text_executable"))):
            rejected += 1
            continue
        if ref in seen_refs or url in seen_urls:
            duplicates += 1
            continue
        seen_refs.add(ref)
        seen_urls.add(url)
        signals.append({
            "signal_id": "last30days:" + sha256((ref + "|" + url).encode()).hexdigest()[:24],
            "title": "Research context: " + topic,
            "title_is_article_headline": False,
            "sector": sector.strip(), "market": market,
            "research_scope_verified": False,
            "primary_source_url": url, "published_at": published.isoformat(),
            "observed_at": generated.isoformat(), "evidence_refs": [ref],
            "source_adapter": "last30days_research_handoff_v1",
            "source_kind": entry["source_type"],
            "independent_corroboration_verified": False,
            "destination_live_verified": False,
        })
    return {
        "schema_version": "empire.organic.last30days_news_intake.v1",
        "mode": "OBSERVE", "signals": signals, "mapped_count": len(signals),
        "rejected_count": rejected, "duplicate_count": duplicates,
        "generated_at": generated.isoformat(), "lookback_days": 30,
        "published_claims_verified": False, "automatic_publication": False,
        "execution_authority": "none",
    }


def attach_gsc_query_page_observations(
    signals: Sequence[Mapping[str, Any]], *,
    reader: GoogleSearchConsoleAdapter | SearchIntelligenceLoopbackGSCReader,
    as_of: str,
    start_date: str,
    end_date: str,
    query_by_signal_id: Mapping[str, str],
    destination_by_signal_id: Mapping[str, str],
    limit: int = 1000,
) -> dict[str, Any]:
    """Attach historical GSC query+owned-page observations using existing reader.

    Requires a real GoogleSearchConsoleAdapter instance, an available reader
    status and exact signal/query/page linkage. Counts describe historical
    search analytics, NOT traffic attributed to the news signal itself.
    """
    clock = _timestamp(as_of)
    if clock is None or not isinstance(
        reader, (GoogleSearchConsoleAdapter, SearchIntelligenceLoopbackGSCReader)
    ):
        raise ValueError("approved first-party GSC reader and timestamp required")
    if not isinstance(signals, (list, tuple)) or len(signals) > 100:
        raise ValueError("bounded signals required")
    if not all(isinstance(row, Mapping) for row in signals):
        raise ValueError("mapping signals required")
    if not isinstance(query_by_signal_id, Mapping) or not isinstance(destination_by_signal_id, Mapping):
        raise ValueError("exact lookup mappings required")
    status = reader.status()
    if not (status.enabled and status.configured and status.available):
        raise SearchConsoleUnavailable("configured_search_console_reader_unavailable")
    site = status.site_url or ""
    if site not in ("sc-domain:empire-ai.co.uk", "https://empire-ai.co.uk/",
                    "https://www.empire-ai.co.uk/"):
        raise ValueError("GSC site must be approved Empire AI property")
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("ISO date-only GSC window required") from exc
    if not (start <= end <= clock and end - start <= timedelta(days=34)
            and clock - end <= timedelta(days=35)
            and type(limit) is int and 1 <= limit <= 5000):
        raise ValueError("GSC window/limit outside review bounds")

    # Invoke the existing GSC Search Analytics reader; no new API transport.
    raw_rows = reader.observations(
        start_date=start_date, end_date=end_date, limit=limit,
    )
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates: set[tuple[str, str]] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        keys = raw.get("keys")
        if (not isinstance(keys, (list, tuple)) or len(keys) != 2
                or not all(isinstance(k, str) for k in keys)):
            continue
        query, page = keys
        page_url = _public_https(page)
        if (not page_url or page_url != page or
                not 2 <= len(query.strip()) <= 180 or
                (page_url and urlsplit(page_url).hostname not in OWNED_HOSTS)):
            continue
        clicks, impressions = raw.get("clicks"), raw.get("impressions")
        if (type(clicks) is not int or type(impressions) is not int
                or not 0 <= clicks <= impressions):
            continue
        # Distinct query/page combinations must not be silently double-counted.
        if (query, page_url) in observed:
            observed.pop((query, page_url), None)
            duplicates.add((query, page_url))
            continue
        if (query, page_url) in duplicates:
            continue
        proof = json.dumps({
            "site": site, "date_range": [start_date, end_date],
            "query": query, "page": page_url,
            "clicks": clicks, "impressions": impressions,
        }, sort_keys=True)
        observed[(query, page_url)] = {
            "source_kind": "GSC", "trusted_reader_verified": True,
            "query": query, "observed_at": clock.isoformat(),
            "clicks": clicks, "impressions": impressions,
            "source_ref": "gsc:query_page:" + sha256(proof.encode()).hexdigest(),
            "observation_window": [start_date, end_date],
            "metric_scope": "historical_query_page_not_news_attribution",
        }
    output = []
    matched = 0
    for item in signals:
        row = dict(item)
        signal_id = row.get("signal_id")
        query = query_by_signal_id.get(signal_id) if isinstance(signal_id, str) else None
        dest = destination_by_signal_id.get(signal_id) if isinstance(signal_id, str) else None
        canonical = _public_https(dest)
        if (isinstance(query, str) and isinstance(dest, str) and dest == canonical
                and canonical is not None
                and urlsplit(canonical).hostname in OWNED_HOSTS
                and (query, canonical) in observed):
            row["search_observation"] = observed[(query, canonical)]
            # Owning exact page is not proof that it is live NOW.
            row["destination_url"] = canonical
            row["destination_live_verified"] = False
            row.pop("destination_evidence_refs", None)
            matched += 1
        output.append(row)
    return {
        "schema_version": "empire.organic.gsc_news_evidence.v1",
        "mode": "OBSERVE", "signals": output,
        "gsc_rows_observed": len(raw_rows), "exact_matches": matched,
        "read_window": [start_date, end_date],
        "news_attributed_clicks": None,
        "live_destination_verified": False,
        "execution_authority": "none",
    }



class SearchIntelligenceLoopbackGSCReader:
    """Read existing authenticated Search Intelligence's loopback projection.

    Fetches ONLY localhost:8771 and only the existing GSC read API.
    Does not access credentials, call Google directly, crawl or write data.
    """

    base_url = "http://127.0.0.1:8771/v1/search"

    def _get(self, path: str, query: dict[str, str] | None = None) -> Mapping[str, Any]:
        from urllib.request import build_opener, HTTPRedirectHandler
        from urllib.parse import urlencode

        class RejectRedirects(HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                raise SearchConsoleUnavailable("loopback_redirect_rejected")

        suffix = "?" + urlencode(query) if query else ""
        try:
            with build_opener(RejectRedirects).open(
                self.base_url + path + suffix, timeout=12,
            ) as response:
                if getattr(response, "status", 200) != 200:
                    raise SearchConsoleUnavailable("loopback_non_200")
                payload = response.read(512_001)
                if len(payload) > 512_000:
                    raise SearchConsoleUnavailable("loopback_response_too_large")
            data = json.loads(payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise SearchConsoleUnavailable("search_intelligence_loopback_unavailable") from exc
        if not isinstance(data, Mapping):
            raise SearchConsoleUnavailable("loopback_invalid_json_object")
        return data

    def status(self):
        from empire_os.search_intelligence.search_console import SearchConsoleStatus
        row = self._get("/search-console/status")
        site = row.get("site_url")
        if site not in ("sc-domain:empire-ai.co.uk",
                        "https://empire-ai.co.uk/",
                        "https://www.empire-ai.co.uk/"):
            raise SearchConsoleUnavailable("search_console_wrong_property")
        return SearchConsoleStatus(
            enabled=row.get("enabled") is True,
            configured=row.get("configured") is True,
            available=row.get("available") is True and row.get("reason") == "ready",
            reason=str(row.get("reason") or "unknown")[:90],
            site_url=site,
        )

    def observations(self, *, start_date: str, end_date: str, limit: int = 1000):
        if type(limit) is not int or not 1 <= limit <= 5000:
            raise ValueError("bounded local GSC read required")
        response = self._get("/search-console/observations", {
            "start_date": start_date,
            "end_date": end_date,
            "limit": str(limit),
        })
        if (response.get("available") is not True
                or response.get("source") != "google_search_console"
                or response.get("site_url") != self.status().site_url):
            raise SearchConsoleUnavailable("local_search_console_response_untrusted")
        rows = response.get("items")
        if (not isinstance(rows, list) or len(rows) > limit
                or any(not isinstance(row, Mapping) for row in rows)):
            raise SearchConsoleUnavailable("invalid_local_gsc_rows")
        return tuple(rows)
