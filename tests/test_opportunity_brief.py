from datetime import datetime, timezone

import pytest

from empire_os.opportunity_brief import (
    build_opportunity_brief,
    materialize_opportunity_briefs,
    render_opportunity_brief_markdown,
    write_opportunity_briefs,
)


NOW = datetime(2026, 10, 2, 19, 45, tzinfo=timezone.utc)


def account():
    return {
        "mode": "OBSERVE",
        "entity_id": "entity-1",
        "company_name": "Acme Roofing",
        "company_website": "https://acme.test",
        "canonical_evidence_count": 3,
        "research_observation_count": 4,
        "buyer_intent": False,
        "commercial_intent": False,
        "execution_authority": "none",
        "claim_critic": {
            "blocked_count": 0,
            "all_published_claims_supported": True,
        },
        "claims": [
            {
                "claim_type": "first_party_web_presence_observed",
                "text": "Acme Roofing first-party web presence was observed.",
                "source_refs": ["https://acme.test"],
                "observed": True,
                "verdict": "SUPPORTED",
            },
            {
                "claim_type": "competitor_colisting_observed",
                "text": "Acme Roofing was observed on a competitor source.",
                "source_refs": ["https://directory.test/roofers"],
                "observed": True,
                "verdict": "SUPPORTED",
            },
        ],
    }


def test_build_brief_publishes_only_supported_observed_claims():
    row = account()
    row["claims"].append({
        "claim_type": "unsupported",
        "text": "Acme wants to buy leads.",
        "source_refs": ["https://search.test"],
        "observed": False,
        "verdict": "BLOCKED",
    })
    result = build_opportunity_brief(row, generated_at=NOW)
    assert result["supported_fact_count"] == 2
    assert all(
        "wants to buy" not in fact["text"]
        for fact in result["observed_facts"]
    )
    assert result["review_ready"] is True


def test_brief_keeps_commercial_truth_unknown():
    result = build_opportunity_brief(account(), generated_at=NOW)
    assert {
        "buyer_intent",
        "commercial_demand",
        "territory",
        "buyer_capacity",
        "delivery_route",
        "pricing",
        "commercial_terms",
        "actual_revenue",
    }.issubset(set(result["unknowns"]))
    assert result["send_approved"] is False
    assert result["external_send_allowed"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["capacity_inferred"] is False
    assert result["revenue_inferred"] is False
    assert result["execution_authority"] == "none"


def test_blocked_claim_critic_prevents_review_ready():
    row = account()
    row["claim_critic"]["blocked_count"] = 1
    result = build_opportunity_brief(row, generated_at=NOW)
    assert result["review_ready"] is False


def test_first_party_evidence_required_for_review_ready():
    row = account()
    row["claims"] = [
        claim for claim in row["claims"]
        if claim["claim_type"] != "first_party_web_presence_observed"
    ]
    result = build_opportunity_brief(row, generated_at=NOW)
    assert result["review_ready"] is False


def test_authoritative_or_commercial_input_fails_closed():
    row = account()
    row["execution_authority"] = "internal_write"
    with pytest.raises(ValueError, match="execution authority"):
        build_opportunity_brief(row, generated_at=NOW)

    row = account()
    row["buyer_intent"] = True
    with pytest.raises(ValueError, match="commercial intent"):
        build_opportunity_brief(row, generated_at=NOW)


def test_batch_and_markdown_materialization(tmp_path):
    payload = materialize_opportunity_briefs(
        {"briefs": [account()]},
        generated_at=NOW,
    )
    assert payload["brief_count"] == 1
    assert payload["review_ready_count"] == 1
    assert payload["external_send_allowed"] is False

    paths = write_opportunity_briefs(tmp_path, payload)
    assert len(paths) == 2
    markdown = paths[1].read_text()
    assert "Observed evidence" in markdown
    assert "Opportunities to test" in markdown
    assert "Still unknown" in markdown
    assert "Buyer intent, pricing, capacity" in markdown


def test_markdown_never_changes_authority():
    payload = build_opportunity_brief(account(), generated_at=NOW)
    rendered = render_opportunity_brief_markdown(payload)
    assert "Internal review brief only" in rendered
    assert payload["send_approved"] is False


def test_systemd_refresh_is_runtime_only():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-opportunity-brief.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-opportunity-brief.timer"
    ).read_text()

    assert "scripts/refresh_competitive_intelligence_chain.py" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=30min" in timer
    assert "outbound" not in service.lower()


def test_refresh_chain_keeps_send_and_money_authority_false(
    tmp_path,
    monkeypatch,
):
    import scripts.refresh_opportunity_brief_chain as chain

    audience = {
        "canonical_signal_row_count": 2,
        "latest_observed_at": "2026-10-02T18:00:00+00:00",
        "companies": [],
        "omega_cortex_context": [],
    }
    research = {
        "generated_at": "2026-10-02T19:00:00+00:00",
        "observation_count": 3,
        "actions": [],
    }
    account_briefs = {
        "brief_count": 1,
        "supported_claim_count": 2,
        "blocked_claim_count": 0,
        "briefs": [],
    }
    opportunity = {
        "brief_count": 1,
        "review_ready_count": 1,
        "briefs": [],
    }

    monkeypatch.setattr(
        chain,
        "refresh_competitor_audience_snapshot",
        lambda _root, _writer: audience,
    )
    monkeypatch.setattr(
        chain,
        "execute_snapshot_research",
        lambda _audience, **_kwargs: research,
    )
    monkeypatch.setattr(
        chain,
        "write_account_research_snapshot",
        lambda _root, _payload: tmp_path / "research.json",
    )
    monkeypatch.setattr(
        chain,
        "build_account_brief_batch",
        lambda _audience, _research: account_briefs,
    )
    monkeypatch.setattr(
        chain,
        "write_account_brief_snapshot",
        lambda _root, _payload: tmp_path / "account.json",
    )
    monkeypatch.setattr(
        chain,
        "materialize_opportunity_briefs",
        lambda _payload: opportunity,
    )
    monkeypatch.setattr(
        chain,
        "write_opportunity_briefs",
        lambda _root, _payload: [tmp_path / "latest.json"],
    )

    result = chain.refresh_opportunity_brief_chain(
        tmp_path,
        writer=object(),
        search_fn=lambda *_args, **_kwargs: {},
        fetch_fn=lambda *_args, **_kwargs: None,
    )
    assert result["canonical_signal_row_count"] == 2
    assert result["account_research_observation_count"] == 3
    assert result["supported_claim_count"] == 2
    assert result["review_ready_count"] == 1
    assert result["external_send_allowed"] is False
    assert result["payment_mutation"] is False
    assert result["revenue_recognition"] is False
    assert result["execution_authority"] == "none"


def test_systemd_refreshes_full_evidence_chain():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-opportunity-brief.service"
    ).read_text()
    assert "EnvironmentFile=/etc/empiredb.env" in service
    assert "refresh_competitive_intelligence_chain.py" in service
    assert "run_opportunity_briefs.py" not in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
