"""Bounded, read-only evidence replay for existing SEO → buyer → revenue hooks.

No databases, webhooks, subscribers, models, automation timers, action queues
or providers are written to or invoked by this module. Only reviewed aggregate
snapshots are accepted, and snapshots older than 24 hours never trigger review
recommendations. Never infer a reply, ranking, subscription or revenue from
a source that doesn't demonstrate it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from empire_os.cross_department_hook_review import preview_event_hook


SCHEMA = "empire.revenue_first_hook_evidence_review.v1"
FRESH_SECONDS = 24 * 60 * 60
MAX_FUTURE_SECONDS = 5 * 60


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def _age_state(source: Mapping[str, Any], now: datetime) -> str:
    timestamp = _clock(source.get("observed_at") or source.get("generated_at"))
    if timestamp is None:
        return "UNKNOWN_TIMESTAMP"
    age = (now - timestamp).total_seconds()
    if age < -MAX_FUTURE_SECONDS:
        return "FUTURE_TIMESTAMP"
    if age > FRESH_SECONDS:
        return "STALE"
    return "FRESH"


def _whole_number(value: Any) -> int | None:
    if type(value) is int and 0 <= value <= 10**12:
        return value
    return None


def _submit_review(
    candidates: list[dict[str, Any]], event_type: str, locator: str,
    priority_note: str, source_state: str,
) -> None:
    if source_state != "FRESH":
        return
    preview = preview_event_hook(
        {"event_type": event_type},
        evidence_refs=(locator,),
    )
    matches = preview["matches"]
    if not matches:
        raise ValueError("existing_control_route_not_registered:" + event_type)
    for match in matches:
        if not match["existing_control_fabric_route"]:
            raise ValueError("requested_hook_event_not_wired:" + event_type)
        candidates.append({
            "hook_key": match["hook_key"],
            "event_type": event_type,
            "department": match["department"],
            "priority": match["priority"],
            "evidence_locator": locator,
            "evidence_source_state": source_state,
            "reason": priority_note,
            "review_status": match["status"],
            "external_execution": False,
            "evidence_verified": False,
        })


def review_revenue_first_sources(
    *,
    search_summary: Mapping[str, Any] | None,
    conversion_snapshot: Mapping[str, Any] | None,
    reply_collector: Mapping[str, Any] | None,
    revenue_pulse: Mapping[str, Any] | None,
    website_checks: Mapping[str, Any] | None,
    now: datetime,
    search_console_daily: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare four observable review packets; never dispatch them.

    The evidence locators are fixed contract paths, not free-form source data.
    Search API responses lack timestamps; a trusted caller must attach its
    observed_at time upon a *successful* bounded GET.
    """
    if now.tzinfo is None:
        raise ValueError("aware_utc_review_clock_required")
    now = now.astimezone(timezone.utc)
    candidates: list[dict[str, Any]] = []
    status: dict[str, dict[str, Any]] = {}

    search = search_summary or {}
    search_age = _age_state(search, now)
    search_valid = (
        search_age == "FRESH"
        and search.get("module") == "empire-search-intelligence"
        and search.get("execution_mode") == "OBSERVE"
        and search.get("api_contract_version") == "search-v1"
        and search.get("repository_available") is True
        and isinstance(search.get("stored_metrics"), Mapping)
    )
    metrics = search.get("stored_metrics") if search_valid else {}
    recorded_opportunities = _whole_number(metrics.get("opportunities"))
    indexed_records = _whole_number(metrics.get("indexed_pages"))
    serp = search.get("serp_source") if isinstance(search.get("serp_source"), Mapping) else {}
    serp_proven = serp.get("rank_positions_attested") is True
    search_ready = bool(
        search_valid and isinstance(search.get("search_console"), Mapping)
        and search["search_console"].get("available") is True
    )
    # Google Search Console's daily aggregate is separate evidence from the
    # canonical Search Intelligence repository. A zero repository count is NOT
    # evidence of zero impressions, indexation or rankings in Google.
    daily = search_console_daily or {}
    daily_age = _age_state(daily, now)
    daily_rows = daily.get("items")
    daily_rows = daily_rows if isinstance(daily_rows, list) else []
    daily_valid = bool(
        daily_age == "FRESH"
        and daily.get("available") is True
        and daily.get("source") == "google_search_console"
        and daily.get("site_url") == "sc-domain:empire-ai.co.uk"
        and daily.get("dimensions") == ["date"]
        and _whole_number(daily.get("count")) == len(daily_rows)
        and len(daily_rows) <= 14
    )
    total_clicks = 0
    total_impressions = 0
    daily_dates: set[date] = set()
    if daily_valid:
        start = now.date() - timedelta(days=7)
        end = now.date() - timedelta(days=1)
        for row in daily_rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("keys"), list):
                daily_valid = False
                break
            keys = row["keys"]
            if len(keys) != 1 or not isinstance(keys[0], str):
                daily_valid = False
                break
            try:
                day = date.fromisoformat(keys[0])
            except ValueError:
                daily_valid = False
                break
            clicks = _whole_number(row.get("clicks"))
            impressions = _whole_number(row.get("impressions"))
            if (day < start or day > end or day in daily_dates
                    or clicks is None or impressions is None or clicks > impressions):
                daily_valid = False
                break
            daily_dates.add(day)
            total_clicks += clicks
            total_impressions += impressions
    if not daily_valid:
        total_clicks = 0
        total_impressions = 0
        daily_dates.clear()
    status["search_intelligence"] = {
        "source_state": search_age if not search_valid else "FRESH",
        "contract_valid": bool(search_valid),
        "gsc_adapter_available": search_ready,
        "gsc_daily_aggregate_source_state": daily_age,
        "gsc_daily_aggregate_valid": daily_valid,
        "gsc_observed_days": len(daily_dates) if daily_valid else None,
        "gsc_observed_impressions": total_impressions if daily_valid else None,
        "gsc_observed_clicks": total_clicks if daily_valid else None,
        "gsc_window_start": (now.date() - timedelta(days=7)).isoformat() if daily_valid else None,
        "gsc_window_end": (now.date() - timedelta(days=1)).isoformat() if daily_valid else None,
        "gsc_zero_clicks_observed": daily_valid and total_impressions > 0 and total_clicks == 0,
        "stored_opportunity_count": recorded_opportunities,
        "stored_indexation_record_count": indexed_records,
        "serp_rank_attestation_verified": serp_proven,
        "google_indexation_inferred_from_zero": False,
        "SEO_results_claim_allowed": False,
        "interpretation": (
            "MEASUREMENT_EVIDENCE_INCOMPLETE" if search_valid
            and (recorded_opportunities in (None, 0) or not serp_proven)
            else "SEARCH_AGGREGATE_UNAVAILABLE" if not search_valid
            else "FURTHER_RESULT_VERIFICATION_REQUIRED"
        ),
    }
    if search_valid and (recorded_opportunities in (None, 0) or not serp_proven):
        _submit_review(
            candidates, "search_intelligence_refresh_requested",
            "loopback:/v1/search/summary",
            "Verify real query/page evidence before promoting SEO opportunity claims",
            search_age,
        )

    conversion = conversion_snapshot or {}
    conversion_age = _age_state(conversion, now)
    stage_counts = conversion.get("counts", {})
    stage = (
        stage_counts.get("delivered_outreach_to_reply", {})
        if isinstance(stage_counts, Mapping) else {}
    )
    stage = stage if isinstance(stage, Mapping) else {}
    entrants = _whole_number(stage.get("entered"))
    converted = _whole_number(stage.get("converted"))
    minimum = _whole_number(conversion.get("min_sample_size"))
    conversion_valid = (
        conversion.get("mode") == "OBSERVE"
        and conversion_age == "FRESH"
        and isinstance(stage_counts, Mapping)
        and minimum is not None
        and minimum >= 1
        and entrants is not None
        and converted is not None
        and converted <= entrants
        and conversion.get("primary_bottleneck") == "delivered_outreach_to_reply"
        and conversion.get("actual_revenue") is False
    )
    meets_sample = bool(conversion_valid and entrants >= minimum)
    status["conversion"] = {
        "source_state": conversion_age,
        "contract_valid": bool(conversion_valid),
        "observed_delivered_to_reply_entries": entrants if conversion_valid else None,
        "observed_delivered_to_reply_transitions": converted if conversion_valid else None,
        "minimum_review_sample": minimum if conversion_valid else None,
        "sample_sufficient": meets_sample,
        "stage_transition_bottleneck_review_ready": meets_sample,
        "actual_customer_replies_proven_by_this_aggregate": False,
        "interpretation": (
            "BUYER_REPLY_STAGE_BOTTLENECK" if meets_sample and converted == 0
            else "NO_SUFFICIENT_CONVERSION_EVIDENCE"
        ),
    }
    if meets_sample and converted == 0:
        _submit_review(
            candidates, "conversion_refresh_requested",
            "runtime:conversion/latest.json",
            "Review qualified reply bottleneck; do not infer zero total mailbox replies",
            conversion_age,
        )

    collector = reply_collector or {}
    reply_age = _age_state(collector, now)
    messages = _whole_number(collector.get("canonical_messages"))
    candidates_admitted = _whole_number(collector.get("candidate_records_admitted"))
    reply_valid = (
        reply_age == "FRESH"
        and collector.get("status") == "READ_SUCCESS"
        and collector.get("source_query_completed") is True
        and messages is not None
        and candidates_admitted is not None
    )
    buyer_proven = (
        reply_valid and messages > 0
        and collector.get("authenticated_buyers_proved") is True
    )
    status["buyer_replies"] = {
        "source_state": reply_age,
        "contract_valid": bool(reply_valid),
        "canonical_message_count": messages if reply_valid else None,
        "candidate_records_admitted": candidates_admitted if reply_valid else None,
        "authenticated_buyer_reply_proven": bool(buyer_proven),
        "buyer_reply_received_event_emitted": False,
        "interpretation": (
            "NO_CANONICAL_BUYER_REPLY_PROOF" if reply_valid and not buyer_proven
            else "BUYER_SOURCE_REVIEW_REQUIRED" if buyer_proven
            else "REPLY_OBSERVER_EVIDENCE_UNAVAILABLE"
        ),
    }
    if reply_valid:
        _submit_review(
            candidates, "reply_analysis_requested",
            "runtime:conversations_replies_control/collector_health_latest.json",
            "Reconcile canonical buyer reply identity; drafts only, no automatic send",
            reply_age,
        )

    revenue = revenue_pulse or {}
    revenue_age = _age_state(revenue, now)
    truth = revenue.get("recognized_revenue_truth")
    truth = truth if isinstance(truth, Mapping) else {}
    recognized = _whole_number(truth.get("recognized_revenue_cents"))
    realized_gp = _whole_number(truth.get("realized_gp_cents"))
    revenue_valid = (
        revenue_age == "FRESH"
        and revenue.get("schema_version") == "empire.revenue-pulse.v3"
        and revenue.get("mode") == "OBSERVE"
        and recognized is not None
        and realized_gp is not None
        and truth.get("forecast_included_in_truth") is False
    )
    status["revenue_pulse"] = {
        "source_state": revenue_age,
        "contract_valid": bool(revenue_valid),
        "recognized_revenue_cents_in_snapshot": recognized if revenue_valid else None,
        "realized_gp_cents_in_snapshot": realized_gp if revenue_valid else None,
        "payment_verified_event_emitted": False,
        "revenue_recognized_event_emitted": False,
        "interpretation": (
            "RECOGNIZED_REVENUE_ZERO_IN_SNAPSHOT" if revenue_valid and recognized == 0
            else "REVENUE_EVIDENCE_REVIEW_REQUIRED" if revenue_valid
            else "REVENUE_EVIDENCE_UNAVAILABLE"
        ),
    }
    if revenue_valid:
        _submit_review(
            candidates, "revenue_pulse_refreshed",
            "runtime:revenue_pulse/latest.json",
            "Review revenue truth and unblock actual accepted, payable buyer outcomes",
            revenue_age,
        )

    public = website_checks or {}
    observations = public.get("pages")
    pages = observations if isinstance(observations, Mapping) else {}
    expected = ("/", "/about", "/commercial", "/insights/revenue-opportunity-assessment")
    website_available = all(pages.get(path) == 200 for path in expected)
    status["flagship_website"] = {
        "source_state": "READ_ONLY_HTTP" if pages else "NOT_CHECKED",
        "checked_routes": len(pages),
        "core_buyer_journey_routes_reachable": website_available,
        "buyer_enquiry_submitted": False,
        "gsc_indexation_verified": False,
        "real_visitor_conversion_verified": False,
        "interpretation": (
            "PUBLIC_PAGE_ROUTES_REACHABLE_CONVERSIONS_UNVERIFIED"
            if website_available else "LIVE_ROUTE_CHECK_INCOMPLETE"
        ),
    }

    # Fixed ordering ensures repeated reviews do not duplicate internal work.
    candidates.sort(key=lambda x: (-x["priority"], x["hook_key"]))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "existing_hook_candidates": candidates,
        "candidate_count": len(candidates),
        "source_status": status,
        "execution_authority": "none",
        "requires_provenance_reconciliation": True,
        "events_emitted": 0,
        "jobs_dispatched": 0,
        "models_invoked": 0,
        "buyer_replies_sent": 0,
        "newsletter_sends": 0,
        "payments_executed": 0,
        "database_writes": 0,
    }
