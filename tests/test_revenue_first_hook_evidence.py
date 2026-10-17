"""Real-evidence hook replay must never manufacture SEO, buyer or revenue proof."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.revenue_first_hook_evidence import (
    review_revenue_first_sources,
)
from scripts import review_revenue_first_hook_evidence as runner


NOW = datetime(2026, 10, 17, 17, 0, tzinfo=timezone.utc)


def sources(clock: datetime = NOW) -> dict:
    stamp = (clock - timedelta(minutes=2)).isoformat()
    return {
        "search_summary": {
            "module": "empire-search-intelligence",
            "api_contract_version": "search-v1",
            "execution_mode": "OBSERVE",
            "repository_available": True,
            "observed_at": stamp,
            "stored_metrics": {
                "pages": 0, "opportunities": 0,
                "indexed_pages": 0, "open_alerts": 0,
            },
            "search_console": {"available": True},
            "serp_source": {"rank_positions_attested": False},
            "sensitive_provider_token": "SECRET_SHOULD_NOT_ESCAPE",
        },
        "search_console_daily": {
            "available": True,
            "source": "google_search_console",
            "site_url": "sc-domain:empire-ai.co.uk",
            "dimensions": ["date"],
            "count": 5,
            "observed_at": stamp,
            "items": [
                {"keys": ["2026-10-10"], "clicks": 0, "impressions": 1, "position": 7},
                {"keys": ["2026-10-12"], "clicks": 0, "impressions": 3, "position": 2},
                {"keys": ["2026-10-14"], "clicks": 0, "impressions": 2, "position": 7.5},
                {"keys": ["2026-10-15"], "clicks": 0, "impressions": 8, "position": 23},
                {"keys": ["2026-10-16"], "clicks": 0, "impressions": 1, "position": 74},
            ],
            "raw_query": "private-unapproved-query",
        },
        "founder_mailbox_summary": {
            "provider": "empiredb_canonical_replies",
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "canonical_buyer_conversation_verified": False,
            "suppression_evidence_complete": False,
            "observed_at": stamp,
            "summary": {
                "all": 14,
                "replies": 0,
                "verified_canonical_buyer_replies": 0,
                "suppressed": 4,
                "provider_only_reply_evidence": True,
            },
            "identity": {"sender_email": "NEVER_EXPOSE_INTERNAL_SENDER_ADDRESS"},
        },
        "conversion_snapshot": {
            "observed_at": stamp,
            "mode": "OBSERVE",
            "actual_revenue": False,
            "primary_bottleneck": "delivered_outreach_to_reply",
            "min_sample_size": 20,
            "counts": {
                "delivered_outreach_to_reply": {"entered": 52, "converted": 0},
            },
            "raw_contact_email": "private@example.test",
        },
        "reply_collector": {
            "observed_at": stamp,
            "status": "READ_SUCCESS",
            "source_query_completed": True,
            "canonical_messages": 0,
            "candidate_records_admitted": 5,
            "authenticated_buyers_proved": False,
            "unreviewed_buyer_phone": "+441234567890",
        },
        "revenue_pulse": {
            "generated_at": stamp,
            "schema_version": "empire.revenue-pulse.v3",
            "mode": "OBSERVE",
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
                "forecast_included_in_truth": False,
            },
            "provider_payment_reference": "BANK_REFERENCE_SHOULD_NOT_ESCAPE",
        },
        "website_checks": {
            "pages": {
                "/": 200, "/about": 200,
                "/commercial": 200, "/insights/revenue-opportunity-assessment": 200,
            },
        },
    }


def review(**changes):
    kwargs = sources()
    kwargs.update(changes)
    return review_revenue_first_sources(**kwargs, now=NOW)


def test_realistic_zero_revenue_snapshots_generate_four_inert_reviews():
    result = review()
    assert result["mode"] == "OBSERVE"
    assert result["candidate_count"] == 4
    assert [c["hook_key"] for c in result["existing_hook_candidates"]] == [
        "buyer_reply_evidence_review",
        "conversion_snapshot_review",
        "revenue_snapshot_closure_review",
        "seo_source_integrity_review",
    ]
    assert result["source_status"]["conversion"]["observed_delivered_to_reply_entries"] == 52
    assert result["source_status"]["conversion"]["observed_delivered_to_reply_transitions"] == 0
    assert result["source_status"]["buyer_replies"]["authenticated_buyer_reply_proven"] is False
    mailbox = result["source_status"]["founder_mailbox"]
    assert mailbox["contract_valid"] is True
    assert mailbox["recorded_thread_or_mailbox_rows"] == 14
    assert mailbox["suppressed_record_rows"] == 4
    assert mailbox["verified_canonical_buyer_reply_rows"] == 0
    assert mailbox["general_gmail_inbox_was_queried"] is False
    assert mailbox["actual_gmail_reply_absence_inferred"] is False
    assert result["source_status"]["search_intelligence"]["stored_opportunity_count"] == 0
    assert result["source_status"]["search_intelligence"]["gsc_adapter_available"] is True
    assert result["source_status"]["search_intelligence"]["gsc_daily_aggregate_valid"] is True
    assert result["source_status"]["search_intelligence"]["gsc_observed_days"] == 5
    assert result["source_status"]["search_intelligence"]["gsc_observed_impressions"] == 15
    assert result["source_status"]["search_intelligence"]["gsc_observed_clicks"] == 0
    assert result["source_status"]["search_intelligence"]["gsc_zero_clicks_observed"] is True
    assert result["source_status"]["search_intelligence"]["google_indexation_inferred_from_zero"] is False
    assert result["source_status"]["flagship_website"]["core_buyer_journey_routes_reachable"] is True
    assert result["source_status"]["flagship_website"]["real_visitor_conversion_verified"] is False
    assert result["source_status"]["revenue_pulse"]["recognized_revenue_cents_in_snapshot"] == 0
    assert result["source_status"]["revenue_pulse"]["revenue_recognized_event_emitted"] is False
    for field in ("events_emitted", "jobs_dispatched", "models_invoked", "buyer_replies_sent", "newsletter_sends", "payments_executed", "database_writes"):
        assert result[field] == 0
    assert all(c["external_execution"] is False for c in result["existing_hook_candidates"])
    assert all(c["evidence_verified"] is False for c in result["existing_hook_candidates"])
    raw = json.dumps(result)
    for secret in ("SECRET_SHOULD_NOT_ESCAPE", "private@example.test", "+441234567890", "BANK_REFERENCE_SHOULD_NOT_ESCAPE", "private-unapproved-query", "NEVER_EXPOSE_INTERNAL_SENDER_ADDRESS"):
        assert secret not in raw


def test_stale_snapshots_do_not_trigger_internal_review():
    old = sources(NOW - timedelta(days=3))
    result = review(**{k: old[k] for k in (
        "search_summary", "conversion_snapshot", "reply_collector", "revenue_pulse"
    )})
    assert result["candidate_count"] == 0
    for key in ("search_intelligence", "conversion", "buyer_replies", "revenue_pulse"):
        assert result["source_status"][key]["source_state"] == "STALE"


def test_future_dated_snapshots_do_not_trigger():
    future = sources(NOW + timedelta(days=1))
    result = review(**{k: future[k] for k in (
        "search_summary", "conversion_snapshot", "reply_collector", "revenue_pulse"
    )})
    assert result["candidate_count"] == 0
    assert all(
        result["source_status"][key]["source_state"] == "FUTURE_TIMESTAMP"
        for key in ("search_intelligence", "conversion", "buyer_replies", "revenue_pulse")
    )


def test_small_conversion_sample_does_not_claim_bottleneck():
    record = sources()["conversion_snapshot"]
    record["counts"]["delivered_outreach_to_reply"] = {"entered": 5, "converted": 0}
    result = review(conversion_snapshot=record)
    assert result["source_status"]["conversion"]["sample_sufficient"] is False
    assert "conversion_snapshot_review" not in [c["hook_key"] for c in result["existing_hook_candidates"]]


def test_impossible_conversion_counts_fail_closed():
    record = sources()["conversion_snapshot"]
    record["counts"]["delivered_outreach_to_reply"] = {"entered": 52, "converted": 53}
    result = review(conversion_snapshot=record)
    assert result["source_status"]["conversion"]["contract_valid"] is False
    assert "conversion_snapshot_review" not in [c["hook_key"] for c in result["existing_hook_candidates"]]


def test_verified_sounding_misleading_buyer_count_never_emits_buyer_reply_received():
    record = sources()["reply_collector"]
    record["canonical_messages"] = 5
    record["authenticated_buyers_proved"] = True
    result = review(reply_collector=record)
    assert result["source_status"]["buyer_replies"]["authenticated_buyer_reply_proven"] is True
    assert result["source_status"]["buyer_replies"]["buyer_reply_received_event_emitted"] is False
    assert "buyer_reply_priority" not in [c["hook_key"] for c in result["existing_hook_candidates"]]
    assert "buyer_reply_evidence_review" in [c["hook_key"] for c in result["existing_hook_candidates"]]


def test_revenue_positive_count_does_not_grant_payment_or_revenue_events():
    record = sources()["revenue_pulse"]
    record["recognized_revenue_truth"]["recognized_revenue_cents"] = 1_000_000
    result = review(revenue_pulse=record)
    assert result["source_status"]["revenue_pulse"]["recognized_revenue_cents_in_snapshot"] == 1_000_000
    assert result["source_status"]["revenue_pulse"]["revenue_recognized_event_emitted"] is False
    assert "recognized_revenue_feedback" not in [c["hook_key"] for c in result["existing_hook_candidates"]]
    assert result["payments_executed"] == 0


def test_no_indexation_count_cannot_be_presented_as_google_results():
    record = sources()["search_summary"]
    record["stored_metrics"]["indexed_pages"] = 0
    record["serp_source"]["rank_positions_attested"] = False
    result = review(search_summary=record)
    status = result["source_status"]["search_intelligence"]
    assert status["stored_indexation_record_count"] == 0
    assert status["google_indexation_inferred_from_zero"] is False
    assert status["SEO_results_claim_allowed"] is False


def test_missing_or_invalid_sources_only_produce_available_candidate_reviews():
    result = review(
        search_summary=None,
        conversion_snapshot={"mode": "OBSERVE", "counts": {"delivered_outreach_to_reply": {"entered": 52}}},
        reply_collector=None,
        revenue_pulse=None,
        website_checks=None,
    )
    assert result["candidate_count"] == 0
    assert result["source_status"]["flagship_website"]["source_state"] == "NOT_CHECKED"
    assert result["source_status"]["revenue_pulse"]["recognized_revenue_cents_in_snapshot"] is None


def test_script_does_not_call_live_services_when_mocked(tmp_path, monkeypatch):
    root = tmp_path / "site"
    for name, rel in runner.SOURCES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(sources()[name]))
    monkeypatch.setattr(runner, "_search_summary", lambda _clock: sources()["search_summary"])
    monkeypatch.setattr(runner, "_search_console_daily", lambda _clock: sources()["search_console_daily"])
    monkeypatch.setattr(runner, "_founder_mailbox_summary", lambda _clock: sources()["founder_mailbox_summary"])
    monkeypatch.setattr(runner, "_website_route_status", lambda: sources()["website_checks"])
    result = runner.run(root=root, include_public_website=True, now=NOW)
    assert result["candidate_count"] == 4
    assert result["events_emitted"] == 0
    assert result["newsletter_sends"] == 0
    assert result["payments_executed"] == 0


def test_cli_restricts_sources_to_existing_known_files_and_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_search_summary", lambda _clock: sources()["search_summary"])
    monkeypatch.setattr(runner, "_search_console_daily", lambda _clock: sources()["search_console_daily"])
    monkeypatch.setattr(runner, "_founder_mailbox_summary", lambda _clock: sources()["founder_mailbox_summary"])
    result = runner.run(root=tmp_path, include_public_website=False, now=NOW)
    assert result["candidate_count"] == 1
    assert result["existing_hook_candidates"][0]["hook_key"] == "seo_source_integrity_review"


def test_naive_review_clock_fails_closed():
    with pytest.raises(ValueError, match="aware_utc_review_clock_required"):
        review_revenue_first_sources(
            **sources(), now=datetime(2026, 10, 17, 17, 0),
        )


def test_gsc_daily_count_duplicate_date_or_spurious_clicks_are_rejected():
    bad=sources()["search_console_daily"]
    bad["items"][0]["clicks"]=10
    result=review(search_console_daily=bad)
    gsc=result["source_status"]["search_intelligence"]
    assert not gsc["gsc_daily_aggregate_valid"]
    assert gsc["gsc_observed_impressions"] is None
    assert not gsc["gsc_zero_clicks_observed"]
    bad=sources()["search_console_daily"]
    bad["items"][1]["keys"]=["2026-10-10"]
    result=review(search_console_daily=bad)
    assert not result["source_status"]["search_intelligence"]["gsc_daily_aggregate_valid"]


def test_gsc_daily_empty_or_invalid_does_not_mean_no_google_traffic():
    result=review(search_console_daily=None)
    gsc=result["source_status"]["search_intelligence"]
    assert gsc["gsc_observed_impressions"] is None
    assert gsc["gsc_observed_clicks"] is None
    assert gsc["google_indexation_inferred_from_zero"] is False
    assert gsc["SEO_results_claim_allowed"] is False


def test_stale_gsc_daily_response_cannot_claim_impressions():
    bad=sources()["search_console_daily"]
    bad["observed_at"]=(NOW-timedelta(days=8)).isoformat()
    result=review(search_console_daily=bad)
    assert result["source_status"]["search_intelligence"]["gsc_daily_aggregate_source_state"]=="STALE"
    assert result["source_status"]["search_intelligence"]["gsc_observed_impressions"] is None

def test_founder_mailbox_is_not_general_gmail_and_cannot_assert_buyer_identity():
    result=review()
    box=result["source_status"]["founder_mailbox"]
    assert box["provider"]=="empiredb_canonical_replies"
    assert box["interpretation"]=="EMPIREDB_PROVIDER_ONLY_NOT_GMAIL_INBOX"
    assert box["provider_reply_rows"]==0
    assert box["verified_canonical_buyer_reply_rows"]==0
    assert box["suppression_proof_complete"] is False
    assert box["general_gmail_inbox_was_queried"] is False
    assert result["buyer_replies_sent"]==0


def test_false_mailbox_authentication_or_forged_reply_totals_fail_closed():
    source=sources()["founder_mailbox_summary"]
    source["canonical_buyer_conversation_verified"]=True
    result=review(founder_mailbox_summary=source)
    assert result["source_status"]["founder_mailbox"]["contract_valid"] is False
    assert result["source_status"]["founder_mailbox"]["verified_canonical_buyer_reply_rows"] is None
    source=sources()["founder_mailbox_summary"]
    source["summary"]["verified_canonical_buyer_replies"]=5
    result=review(founder_mailbox_summary=source)
    assert result["source_status"]["founder_mailbox"]["contract_valid"] is False
    assert result["source_status"]["founder_mailbox"]["verified_canonical_buyer_reply_rows"] is None


def test_stale_mailbox_aggregate_does_not_stand_in_for_live_gmail():
    source=sources()["founder_mailbox_summary"]
    source["observed_at"]=(NOW-timedelta(days=3)).isoformat()
    result=review(founder_mailbox_summary=source)
    x=result["source_status"]["founder_mailbox"]
    assert x["source_state"]=="STALE"
    assert x["recorded_thread_or_mailbox_rows"] is None
    assert x["actual_gmail_reply_absence_inferred"] is False
