"""Company identity must be genuinely corroborated before reaching Astra."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from empire_os.astra_canonical_company_binding import resolve_company_bindings
from empire_os.astra_executive import build_executive_snapshot

NOW = datetime.now(timezone.utc)
ENTITY = str(uuid4())
PROSPECT = str(uuid4())


def nba(*, action="verify_decision_maker", entity=ENTITY,
        prospect=PROSPECT, name="North Roof Ltd", gate=False):
    return {"generated_at": NOW.isoformat(), "actions": [{
        "entity_id": entity,
        "prospect_id": prospect,
        "company_name": name,
        "recommended_action": action,
        "authority": "founder_gate" if gate else "internal_write",
        "founder_gate_required": gate,
        "waiting_external": False,
        "evidence": {"ready_observed": True},
    }]}


def scout(*, verified=True, first_party=True, source=None,
          prospect=PROSPECT, name="North Roof Ltd",
          domain="northroof.example", website=None, duplicate=False):
    row = {
        "canonical_seed_prospect_id": prospect,
        "canonical_seed_website": "https://northroof.example/",
        "canonical_identity_verified": verified,
        "canonical_seed_identity_corroborated": first_party,
        "discovery_source": "canonical_prospect_seed",
        "business_name_source": (
            source if source is not None
            else "canonical_seed_corroborated_by_site"
        ),
        "business_name": name,
        "site_business_names": [name],
        "domain": domain,
        "website": website or ("https://" + domain + "/"),
        "explicit_direct_buyer_evidence": False,
        "outreach_authorized": False,
    }
    return {
        "generated_at": NOW.isoformat(),
        "candidates": [row, dict(row)] if duplicate else [row],
    }


def match(a=None, b=None):
    return resolve_company_bindings(a or nba(), b or scout(), now=NOW)


def test_verified_canonical_and_first_party_identity_can_scope_research():
    result = match()
    assert result["status"] == "matched"
    assert result["matched_count"] == 1
    assert result["bindings"][ENTITY]["canonical_prospect_id"] == PROSPECT
    assert result["bindings"][ENTITY]["company_domain"] == "northroof.example"
    assert result["bindings"][ENTITY]["identity_scope"] == "research_only"
    assert result["execution_authority"] == "none"
    assert result["outbound_authorized"] is False


def test_false_canonical_bool_and_unverified_site_cannot_bind():
    assert match(b=scout(verified=False))["matched_count"] == 0
    assert match(b=scout(first_party=False))["matched_count"] == 0
    assert match(b=scout(source="canonical_prospect_seed"))["matched_count"] == 0


def test_unlinked_prospect_cannot_bind_even_when_company_names_match():
    assert match(b=scout(prospect=str(uuid4())))["matched_count"] == 0
    assert match(b=scout(name="Other Roof Ltd"))["matched_count"] == 0


def test_company_domain_lookalike_and_cross_site_denied():
    assert match(b=scout(website="https://northroof.example.attacker.test"))["matched_count"] == 0
    assert match(b=scout(domain="northroof.example.attacker.test"))["matched_count"] == 0
    assert match(b=scout(website="https://northroof.example@evil.test"))["matched_count"] == 0


def test_missing_first_party_observed_name_denied():
    row = scout()
    row["candidates"][0]["site_business_names"] = ["North Rofer Ltd"]
    assert match(b=row)["matched_count"] == 0
    row["candidates"][0]["site_business_names"] = []
    assert match(b=row)["matched_count"] == 0


def test_collision_between_canonical_candidates_fails_closed():
    result = match(b=scout(duplicate=True))
    assert result["matched_count"] == 0
    assert result["blocked_reason_counts"]["canonical_prospect_collision"] == 1


def test_stale_scout_or_nba_does_not_resurrect_domain():
    old = scout()
    old["generated_at"] = (NOW - timedelta(hours=3)).isoformat()
    assert match(b=old)["status"] == "stale_or_missing_source_receipt"
    old = nba()
    old["generated_at"] = (NOW - timedelta(hours=3)).isoformat()
    assert match(a=old)["status"] == "stale_or_missing_source_receipt"


def test_founder_gates_cannot_receive_scope_from_canonical_identity():
    assert match(a=nba(action="payment_review", gate=True))["matched_count"] == 0
    assert match(a=nba(action="send_email"))["matched_count"] == 0
    assert match(a=nba(action="enrich_identity", gate=True))["matched_count"] == 0


def test_missing_uuids_and_self_reported_company_only_denied():
    assert match(a=nba(prospect="not-a-real-prospect-id"))["matched_count"] == 0
    assert match(a=nba(entity="company:smith"))["matched_count"] == 0
    assert match(b=scout(prospect="fake-canonical"))["matched_count"] == 0


def test_astra_plan_binds_only_scoped_research_identity():
    baseline = build_executive_snapshot(
        predictive_status={}, evidence_routes={},
        next_best_action=nba(), revenue_pulse={},
    )
    bound = build_executive_snapshot(
        predictive_status={}, evidence_routes={},
        next_best_action=nba(), revenue_pulse={},
        scout_identity=scout(),
    )
    assert bound["canonical_company_binding_count"] == 1
    assert baseline["canonical_company_binding_count"] == 0
    normal = next(s for s in baseline["plan"] if s["action"] == "verify_decision_maker")
    enriched = next(s for s in bound["plan"] if s["action"] == "verify_decision_maker")
    assert normal["step_id"] == enriched["step_id"]
    assert normal["authority"] == enriched["authority"]
    assert normal["auto_dispatch_eligible"] == enriched["auto_dispatch_eligible"]
    assert "company_domain" not in normal["intelligence_request"]
    assert enriched["intelligence_request"]["company_domain"] == "northroof.example"
    assert enriched["intelligence_request"]["canonical_prospect_id"] == PROSPECT
    assert enriched["intelligence_request"]["identity_scope"] == "research_only"
    assert bound["execution_authority"] == "none"
    assert bound["external_execution_performed"] is False


def test_no_verified_identity_does_not_change_existing_plan_or_authority():
    normal = build_executive_snapshot(
        predictive_status={}, evidence_routes={},
        next_best_action=nba(), revenue_pulse={},
    )
    blocked = build_executive_snapshot(
        predictive_status={}, evidence_routes={},
        next_best_action=nba(), revenue_pulse={},
        scout_identity=scout(verified=False),
    )
    assert normal["plan_id"] == blocked["plan_id"]
    assert normal["plan"] == blocked["plan"]
    assert blocked["canonical_company_binding_count"] == 0


def test_historical_founder_payment_gate_never_receives_identity_scope():
    source = nba(action="payment_review", gate=True)
    payload = build_executive_snapshot(
        predictive_status={}, evidence_routes={},
        next_best_action=source, revenue_pulse={},
        scout_identity=scout(),
    )
    assert payload["canonical_company_binding_count"] == 0
    matching = [s for s in payload["plan"] if s["action"] == "payment_review"]
    assert len(matching) == 1
    assert matching[0]["founder_gate_required"] is True
    assert matching[0]["auto_dispatch_eligible"] is False
    assert "company_domain" not in matching[0]["intelligence_request"]


def test_repeated_same_entity_cannot_reacquire_binding_on_third_duplicate():
    actions = nba()
    actions["actions"] = [dict(actions["actions"][0]) for _ in range(3)]
    result = match(a=actions)
    assert result["matched_count"] == 0
    assert result["bindings"] == {}


def test_canonical_website_is_required_independently_of_site_website():
    row = scout()
    row["candidates"][0].pop("canonical_seed_website")
    assert match(b=row)["matched_count"] == 0
    row["candidates"][0]["canonical_seed_website"] = "https://northroof.example.attacker.test"
    assert match(b=row)["matched_count"] == 0
