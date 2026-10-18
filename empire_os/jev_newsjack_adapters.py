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
