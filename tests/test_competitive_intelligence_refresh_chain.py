from datetime import datetime, timezone
import json

import scripts.refresh_competitive_intelligence_chain as chain


NOW = datetime(2026, 10, 2, 20, 30, tzinfo=timezone.utc)


def research_payload(digest: str):
    return {
        "generated_at": NOW.isoformat(),
        "observation_count": 1,
        "actions": [{
            "entity_id": "entity-1",
            "observations": [{
                "observation_type": "public_first_party_page",
                "url": "https://acme.test/",
                "content_sha256": digest,
            }],
        }],
    }


def test_detect_page_changes_uses_entity_url_and_direct_hash():
    previous = research_payload("a" * 64)
    current = research_payload("b" * 64)
    current["actions"][0]["observations"].append({
        "observation_type": "public_search_result",
        "url": "https://search.test/",
        "content_sha256": None,
    })
    result = chain.detect_page_changes(previous, current)
    assert result["tracked_page_count"] == 1
    assert result["changed_page_count"] == 1
    assert result["new_page_count"] == 0
    assert result["changed_pages"][0]["entity_id"] == "entity-1"
    assert result["execution_authority"] == "none"


def test_new_direct_page_is_not_mislabelled_as_changed():
    result = chain.detect_page_changes({}, research_payload("c" * 64))
    assert result["changed_page_count"] == 0
    assert result["new_page_count"] == 1


def test_refresh_chain_is_failsoft_for_search_and_runs_change_research(
    tmp_path,
    monkeypatch,
):
    config = tmp_path / chain.MARKET_CONFIG
    config.parent.mkdir(parents=True)
    config.write_text("{}")
    research_path = tmp_path / chain.RESEARCH
    research_path.parent.mkdir(parents=True)
    research_path.write_text(json.dumps(research_payload("a" * 64)))

    audience = {
        "canonical_signal_row_count": 4,
        "companies": [{
            "entity_id": "entity-1",
            "company_name": "Acme",
        }],
        "omega_cortex_context": [{
            "entity_id": "entity-1",
            "next_best_research_action": "collect_additional_public_evidence",
        }],
    }
    refreshed = research_payload("b" * 64)
    refreshed["company_count"] = 1

    monkeypatch.setattr(
        chain, "run_market_scale_sweep",
        lambda **_kwargs: {"generated_at": NOW.isoformat()},
    )
    monkeypatch.setattr(
        chain, "write_market_scale_snapshot",
        lambda *_args, **_kwargs: None,
    )
    for name in (
        "refresh_ecosystem_snapshot",
        "refresh_public_review_overlap_snapshot",
        "refresh_public_activity_snapshot",
        "refresh_feed_snapshot",
        "refresh_market_opportunity_snapshot",
    ):
        monkeypatch.setattr(
            chain, name,
            lambda *_args, **_kwargs: {"generated_at": NOW.isoformat()},
        )

    search_calls = {"count": 0}
    def fail_search(*_args, **_kwargs):
        search_calls["count"] += 1
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(chain, "refresh_search_presence_snapshot", fail_search)

    monkeypatch.setattr(
        chain, "refresh_competitor_audience_snapshot",
        lambda *_args, **_kwargs: audience,
    )
    monkeypatch.setattr(
        chain, "execute_snapshot_research",
        lambda *_args, **_kwargs: refreshed,
    )

    change_calls = []
    def fake_change_research(company, context, **_kwargs):
        change_calls.append((company, context))
        return {
            "entity_id": company["entity_id"],
            "requested_action": context["next_best_research_action"],
            "execution_authority": "none",
        }
    monkeypatch.setattr(chain, "execute_account_research", fake_change_research)
    monkeypatch.setattr(
        chain, "write_account_research_snapshot",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        chain, "build_account_brief_batch",
        lambda *_args, **_kwargs: {
            "brief_count": 1,
            "supported_claim_count": 2,
            "blocked_claim_count": 0,
            "briefs": [],
        },
    )
    monkeypatch.setattr(
        chain, "write_account_brief_snapshot",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        chain, "materialize_opportunity_briefs",
        lambda *_args, **_kwargs: {
            "brief_count": 1,
            "review_ready_count": 1,
            "briefs": [],
        },
    )
    monkeypatch.setattr(
        chain, "write_opportunity_briefs",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        chain, "refresh_predictive_cloud_status",
        lambda *_args, **_kwargs: {
            "generated_at": NOW.isoformat(),
            "execution_authority": "none",
        },
    )

    payload = chain.refresh_competitive_intelligence_chain(
        tmp_path,
        writer=object(),
        search_fn=lambda *_args, **_kwargs: {},
        fetch_fn=lambda _url: "<html>Acme</html>",
        now=NOW,
    )

    assert payload["ok"] is True
    assert payload["degraded"] is True
    assert "search_presence" in payload["degraded_stages"]
    stage = next(
        row for row in payload["stages"]
        if row["stage"] == "search_presence"
    )
    assert stage["attempts"] == 2
    assert search_calls["count"] == 2
    assert payload["page_change_detection"]["changed_page_count"] == 1
    assert payload["research_on_change_triggered"] is True
    assert payload["change_research_count"] == 1
    assert change_calls[0][1]["next_best_research_action"] == (
        "deep_account_research"
    )
    assert payload["freshness"] == "FRESH"
    assert payload["expires_at"] == "2026-10-02T22:30:00+00:00"
    assert payload["predictive_cloud_refreshed"] is True
    assert payload["external_send_allowed"] is False
    assert payload["payment_mutation"] is False
    assert payload["revenue_recognition"] is False
    assert payload["execution_authority"] == "none"
    written = json.loads((tmp_path / chain.OUTPUT).read_text())
    assert written["ok"] is True


def test_critical_canonical_failure_marks_cycle_unhealthy(
    tmp_path,
    monkeypatch,
):
    config = tmp_path / chain.MARKET_CONFIG
    config.parent.mkdir(parents=True)
    config.write_text("{}")

    for name in (
        "run_market_scale_sweep",
        "refresh_ecosystem_snapshot",
        "refresh_public_review_overlap_snapshot",
        "refresh_public_activity_snapshot",
        "refresh_feed_snapshot",
        "refresh_market_opportunity_snapshot",
    ):
        monkeypatch.setattr(chain, name, lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        chain, "write_market_scale_snapshot",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        chain, "refresh_search_presence_snapshot",
        lambda *_args, **_kwargs: {},
    )
    def fail_canonical(*_args, **_kwargs):
        raise RuntimeError("canonical reader down")
    monkeypatch.setattr(
        chain, "refresh_competitor_audience_snapshot", fail_canonical
    )
    monkeypatch.setattr(
        chain, "refresh_predictive_cloud_status",
        lambda *_args, **_kwargs: {},
    )

    payload = chain.refresh_competitive_intelligence_chain(
        tmp_path,
        writer=object(),
        now=NOW,
    )
    assert payload["ok"] is False
    assert "canonical_audience" in payload["critical_failures"]
    assert payload["external_send_allowed"] is False
