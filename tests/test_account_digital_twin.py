from empire_os.account_digital_twin import (
    build_account_twin,
    build_account_twin_snapshot,
)


def _buyer_entity():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "prospect_id": "prospect-golden",
        "current_factual_state": "RESEARCHED",
        "observed_true_states": [
            "DISCOVERED",
            "SIGNAL_ACTIVE",
            "RESEARCHED",
        ],
        "unknown_states": [
            "ICP_MATCH",
            "READY",
            "ENGAGED",
            "CONVERSATION",
            "COMMERCIAL_INTENT",
            "TERMS",
            "PAYMENT_PENDING",
            "PAID",
            "FULFILLED",
            "EXPANSION",
        ],
        "states": [
            {
                "state": "DISCOVERED",
                "observed": True,
                "evidence": {
                    "entity_id": "entity-golden",
                    "prospect_id": "prospect-golden",
                },
            },
            {
                "state": "ICP_MATCH",
                "observed": None,
                "evidence": {
                    "qualification_score": 86.2,
                    "qualification_status": "insufficient_evidence",
                },
            },
            {
                "state": "SIGNAL_ACTIVE",
                "observed": True,
                "evidence": {
                    "competitive_signal_count": 3,
                },
            },
            {
                "state": "RESEARCHED",
                "observed": True,
                "evidence": {
                    "supported_claim_count": 3,
                    "blocked_claim_count": 0,
                },
            },
            {
                "state": "READY",
                "observed": None,
                "evidence": {
                    "qualification_score": 86.2,
                    "qualification_status": "insufficient_evidence",
                },
            },
            {
                "state": "CONTACTED",
                "observed": False,
                "evidence": {
                    "contacted_status": "not_contacted",
                    "contacted_at": None,
                },
            },
            *[
                {"state": name, "observed": None, "evidence": {}}
                for name in (
                    "ENGAGED",
                    "CONVERSATION",
                    "COMMERCIAL_INTENT",
                    "TERMS",
                    "PAYMENT_PENDING",
                    "PAID",
                    "FULFILLED",
                    "EXPANSION",
                )
            ],
        ],
    }


def _audience():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "competitors": ["elite-roofing-solar"],
        "competitor_count": 1,
        "unique_evidence_count": 3,
        "evidence": [
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://comparison.example/a",
            },
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://comparison.example/b",
            },
            {
                "competitor_key": "elite-roofing-solar",
                "source_ref": "https://comparison.example/c",
            },
        ],
    }


def _research():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "requested_action": "deep_account_research",
        "next_step": "account_research_brief_ready_for_review",
        "observation_count": 4,
        "observations": [
            {
                "url": "https://goldenspikeroofing.com/",
                "verified_fact": False,
                "observation_type": "public_first_party_page",
            }
        ],
    }


def _brief():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "company_website": "https://goldenspikeroofing.com",
        "claims": [
            {
                "claim_type": "first_party_web_presence_observed",
                "verdict": "SUPPORTED",
                "source_refs": ["https://goldenspikeroofing.com/"],
            }
        ],
        "claim_critic": {
            "supported_count": 1,
            "blocked_count": 0,
            "all_published_claims_supported": True,
        },
    }


def _next_action():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "recommended_action": "research_more",
        "recommendation_only": True,
        "mutation_authorized": False,
        "external_execution_authorized": False,
    }


def _commercial_history():
    return {
        "outbound_intents": [],
        "outbound_replies": [],
        "terms_reviews": [],
        "payment_requests": [],
        "payment_evidence": [],
        "fulfilment_orders": [],
        "commercial_outcomes": [],
    }


def test_twin_composes_identity_research_and_competitor_evidence():
    twin = build_account_twin(
        _buyer_entity(),
        audience=_audience(),
        research=_research(),
        brief=_brief(),
        next_action=_next_action(),
        qualification_history=[{
            "id": "qual-1",
            "entity_id": "entity-golden",
            "prospect_id": "prospect-golden",
            "score": 86.2,
            "tier": "insufficient_evidence",
            "status": "insufficient_evidence",
            "recommended_action": "Collect evidence before commercial action",
        }],
    )

    assert twin["identity"]["company_name"] == "Golden Spike Roofing Inc"
    assert twin["identity"]["company_website"] == (
        "https://goldenspikeroofing.com"
    )
    assert twin["public_evidence"]["supported_claim_count"] == 1
    assert twin["competitor_relationships"]["competitor_count"] == 1
    assert twin["competitor_relationships"]["evidence_count"] == 3
    assert twin["research"]["observation_count"] == 4
    assert twin["qualification"]["history_available"] is True
    assert len(twin["qualification"]["history"]) == 1
    assert twin["next_best_action"]["recommended_action"] == "research_more"


def test_twin_keeps_unknown_commercial_state_unknown():
    twin = build_account_twin(
        _buyer_entity(),
        audience=_audience(),
        research=_research(),
        brief=_brief(),
        next_action=_next_action(),
    )

    assert twin["commercial"]["commercial_intent"] is None
    assert twin["commercial"]["terms"] is None
    assert twin["commercial"]["payment_pending"] is None
    assert twin["commercial"]["paid"] is None
    assert twin["commercial"]["fulfilled"] is None
    assert twin["revenue_truth"]["recognized_revenue_cents"] is None
    assert twin["revenue_truth"]["realized_gp_cents"] is None
    assert twin["revenue_truth"]["actual_revenue"] is False


def test_twin_does_not_convert_scores_or_evidence_into_intent():
    twin = build_account_twin(
        _buyer_entity(),
        audience=_audience(),
        research=_research(),
        brief=_brief(),
        next_action=_next_action(),
    )

    assert twin["qualification"]["score_is_commercial_intent"] is False
    assert twin["competitor_relationships"]["buyer_intent_inferred"] is False
    assert twin["buyer_intent_inferred"] is False
    assert twin["commercial_intent_inferred"] is False
    assert twin["outreach_authorized"] is False
    assert twin["payment_authorized"] is False
    assert twin["execution_authority"] == "none"


def test_twin_represents_missing_history_as_uncertainty():
    twin = build_account_twin(
        _buyer_entity(),
        audience=_audience(),
        research=_research(),
        brief=_brief(),
        next_action=_next_action(),
    )

    assert twin["uncertainty"]["explicit"] is True
    assert "outreach_history_not_observed" in twin["uncertainty"]["items"]
    assert "conversation_not_observed" in twin["uncertainty"]["items"]
    assert twin["qualification"]["history_available"] is False
    assert twin["outreach"]["history_available"] is False
    assert twin["conversation"]["history_available"] is False


def test_snapshot_is_read_only_and_entity_keyed():
    result = build_account_twin_snapshot(
        buyer_state={"entities": [_buyer_entity()]},
        audience={"companies": [_audience()]},
        research={"actions": [_research()]},
        briefs={"briefs": [_brief()]},
        next_actions={"actions": [_next_action()]},
    )

    assert result["twin_count"] == 1
    assert result["twins"][0]["entity_id"] == "entity-golden"
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_authorized"] is False
    assert result["payment_authorized"] is False
    assert result["execution_authority"] == "none"



def test_snapshot_can_attach_qualification_history_by_entity():
    result = build_account_twin_snapshot(
        buyer_state={"entities": [_buyer_entity()]},
        audience={"companies": [_audience()]},
        research={"actions": [_research()]},
        briefs={"briefs": [_brief()]},
        next_actions={"actions": [_next_action()]},
        qualification_history_by_entity={
            "entity-golden": [{
                "id": "qual-1",
                "entity_id": "entity-golden",
                "prospect_id": "prospect-golden",
                "score": 86.2,
                "tier": "insufficient_evidence",
                "status": "insufficient_evidence",
            }]
        },
    )

    twin = result["twins"][0]
    assert twin["qualification"]["history_available"] is True
    assert twin["qualification"]["history"][0]["id"] == "qual-1"



def test_twin_exposes_canonical_commercial_history_without_promoting_state():
    twin = build_account_twin(
        _buyer_entity(),
        audience=_audience(),
        research=_research(),
        brief=_brief(),
        next_action=_next_action(),
        commercial_history=_commercial_history(),
    )

    assert twin["outreach"]["history_available"] is True
    assert twin["outreach"]["intent_count"] == 0
    assert twin["conversation"]["history_available"] is True
    assert twin["conversation"]["reply_count"] == 0
    assert twin["conversation"]["conversation_state_authoritative"] is False
    assert twin["commercial"]["history_available"] is True
    assert twin["commercial"]["terms_reviews"] == []
    assert twin["commercial"]["payment_requests"] == []
    assert twin["commercial"]["payment_evidence"] == []
    assert twin["commercial"]["fulfilment_orders"] == []
    assert twin["outcomes"]["available"] is True
    assert twin["outcomes"]["history"] == []
    assert twin["commercial"]["commercial_intent"] is None
    assert twin["commercial"]["terms"] is None
    assert twin["commercial"]["paid"] is None
    assert twin["buyer_intent_inferred"] is False
    assert twin["commercial_intent_inferred"] is False


def test_snapshot_can_attach_commercial_history_by_entity():
    result = build_account_twin_snapshot(
        buyer_state={"entities": [_buyer_entity()]},
        audience={"companies": [_audience()]},
        research={"actions": [_research()]},
        briefs={"briefs": [_brief()]},
        next_actions={"actions": [_next_action()]},
        commercial_history_by_entity={
            "entity-golden": _commercial_history(),
        },
    )

    twin = result["twins"][0]
    assert twin["outreach"]["history_available"] is True
    assert twin["conversation"]["history_available"] is True
    assert twin["commercial"]["history_available"] is True
    assert twin["outcomes"]["available"] is True
    assert "commercial_history_unavailable" not in twin["uncertainty"]["items"]
