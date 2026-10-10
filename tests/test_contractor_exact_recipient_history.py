"""Only exact read-only EmpireDB intent history for vetted business research routes."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from pathlib import Path
import json

import pytest

import scripts.materialize_company_routed_buyer_review as runner
from empire_os.storm_contractor_review import attach_existing_canonical_contact_history
from scripts.refresh_contractor_revenue_review import run

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 10)


def cohort():
    return run(as_of=AS_OF)


def spc(payload):
    return next(p for p in payload["packets"] if p["company_domain"] == "spcroofs.com")


def test_public_business_address_sources_are_bounded_and_not_a_marketing_clearance():
    reviewed = cohort()
    candidates = runner._review_exact_public_recipient_candidates(reviewed)
    assert candidates == {"info@spcgc.com", "jshaw@spcgc.com"}
    assert reviewed["summary"]["rapport_gate_research_count"] == 8
    assert spc(reviewed)["business_contact_research"]["person_candidate_current_route_verified"] is False
    assert spc(reviewed)["existing_outbound_rapport_policy"]["next_action"] == "RESEARCH"


def test_exact_intent_founder_guard_holds_generic_and_historical_contacts():
    reviewed = cohort()
    checked = attach_existing_canonical_contact_history(
        reviewed, prior_contact_domains=set(), suppressed_emails=set(),
        prior_recipient_intents={"info@spcgc.com", "jshaw@spcgc.com"},
    )
    p = spc(checked)
    assert checked["summary"]["exact_recipient_outbound_intent_checks"] == 2
    assert checked["summary"]["exact_recipient_prior_intent_holds"] == 1
    assert checked["summary"]["exact_recipient_suppression_holds"] == 0
    assert p["first_party_business_email_prior_intent_match"] is True
    assert p["historical_person_email_prior_intent_match"] is True
    assert p["contact_history_state"] == "EXACT_RECIPIENT_INTENT_REVIEW_HOLD"
    assert "RECONCILE_EXACT_RECIPIENT_EXISTING_INTENT_NO_DUPLICATE_OUTREACH" in p["review_tasks"]
    assert not p["outbound_authorized"]
    assert p["suppression_verified_clear"] is False
    assert checked["individual_recipient_suppression_cleared"] is False


def test_zero_exact_intent_matches_does_not_authorize_company_or_person():
    checked = attach_existing_canonical_contact_history(
        cohort(), prior_contact_domains=set(), suppressed_emails=set(),
        prior_recipient_intents=set(),
    )
    p = spc(checked)
    assert p["exact_recipient_outbound_intent_history_checked"] is True
    assert checked["summary"]["exact_recipient_outbound_intent_checks"] == 2
    assert checked["summary"]["exact_recipient_prior_intent_holds"] == 0
    assert p["contact_history_state"] == "NO_DOMAIN_MATCH_RECIPIENT_STILL_UNVERIFIED"
    assert p["recipient_level_suppression_verified"] is False
    assert not p["founder_review_ready"] and not p["outbound_authorized"]


def test_suppression_takes_precedence_over_existing_intent_match():
    checked = attach_existing_canonical_contact_history(
        cohort(), prior_contact_domains=set(),
        suppressed_emails={"info@spcgc.com"},
        prior_recipient_intents={"info@spcgc.com"},
    )
    p = spc(checked)
    assert p["contact_history_state"] == "SUPPRESSED_DOMAIN_CONTACT_HOLD"
    assert p["exact_recipient_prior_intent_match"] is True
    assert checked["summary"]["exact_recipient_suppression_holds"] == 1


def test_no_exact_lookup_input_never_implies_history_check():
    checked = attach_existing_canonical_contact_history(
        cohort(), prior_contact_domains=set(), suppressed_emails=set(),
    )
    assert spc(checked)["exact_recipient_outbound_intent_history_checked"] is False
    assert checked["summary"]["exact_recipient_outbound_intent_checks"] == 0


def test_untrusted_database_result_or_caller_evidence_is_fail_closed():
    d = cohort()
    with pytest.raises(ValueError, match="UNVERIFIED_EXACT_RECIPIENT"):
        attach_existing_canonical_contact_history(
            d, prior_contact_domains=set(), suppressed_emails=set(),
            prior_recipient_intents=["info@spcgc.com"],
        )
    with pytest.raises(ValueError, match="UNVERIFIED_EXACT_RECIPIENT"):
        attach_existing_canonical_contact_history(
            d, prior_contact_domains=set(), suppressed_emails=set(),
            prior_recipient_intents={"INFO@SPCGC.COM"},
        )


@pytest.mark.parametrize("bad", [
    {"info@spcgc.com", "jshaw@spcgc.com", " "},
    {"A"*255 + "@spcgc.com"},
    {"evil@example.com\n"},
    {"not-an-email"},
])
def test_exact_reader_rejects_invalid_candidate_sets_before_db(monkeypatch, bad):
    monkeypatch.setattr(runner.psycopg, "connect", lambda _: (_ for _ in ()).throw(
        AssertionError("must not access DB")
    ))
    with pytest.raises(ValueError, match="INVALID_BOUNDED"):
        runner._canonical_exact_outbound_intents(bad)


def test_exact_reader_empty_candidates_skip_db_even_without_secrets(monkeypatch):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)
    monkeypatch.setattr(runner.psycopg, "connect", lambda _: (_ for _ in ()).throw(
        AssertionError("must not access DB")
    ))
    assert runner._canonical_exact_outbound_intents(set()) == set()


def test_exact_reader_requires_authorised_own_db_connection(monkeypatch):
    monkeypatch.delenv("EMPIREDB_DSN", raising=False)
    with pytest.raises(RuntimeError, match="EMPIREDB_DSN"):
        runner._canonical_exact_outbound_intents({"info@spcgc.com"})


def test_exact_reader_parameterized_read_only_all_intent_states(monkeypatch):
    observed = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params=None):
            observed.append((query, params))
        def fetchall(self): return [("info@spcgc.com",)]
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self): return Cursor()
    monkeypatch.setenv("EMPIREDB_DSN", "test-dsn-not-a-real-password")
    monkeypatch.setattr(runner.psycopg, "connect", lambda _: Connection())
    assert runner._canonical_exact_outbound_intents(
        {"jshaw@spcgc.com", "info@spcgc.com"}
    ) == {"info@spcgc.com"}
    assert observed[0][0] == "SET TRANSACTION READ ONLY"
    assert "statement_timeout" in observed[1][0]
    query, params = observed[2]
    assert "public.outbound_intents" in query
    assert "channel = 'email'" in query
    assert " = ANY(%s)" in query
    assert "status" not in query.lower()
    assert params == (["info@spcgc.com", "jshaw@spcgc.com"],)
    assert "info@spcgc.com" not in query
    assert "jshaw@spcgc.com" not in query


def test_exact_reader_detects_db_return_outside_queried_cohort(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *_): pass
        def fetchall(self): return [("unauthorised@example.org",)]
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self): return Cursor()
    monkeypatch.setenv("EMPIREDB_DSN", "test-dsn")
    monkeypatch.setattr(runner.psycopg, "connect", lambda _: Connection())
    with pytest.raises(ValueError, match="UNTRUSTED_EXACT"):
        runner._canonical_exact_outbound_intents({"info@spcgc.com"})


def test_exact_source_authority_must_not_be_fabricated():
    payload = cohort()
    spc(payload)["business_contact_research"]["outbound_authorized"] = True
    with pytest.raises(ValueError, match="UNTRUSTED_PUBLIC_CONTACT"):
        runner._review_exact_public_recipient_candidates(payload)


def test_exact_check_is_not_outbound_or_mail_authorization():
    checked = attach_existing_canonical_contact_history(
        cohort(), prior_contact_domains=set(), suppressed_emails=set(),
        prior_recipient_intents=set(),
    )
    assert checked["summary"]["independently_verified_purchase_intent"] == 0
    assert checked["summary"]["approved_outbound_count"] == 0
    assert checked["outbound_authorized"] is False
    assert checked["contract_sent"] is False
    for p in checked["packets"]:
        assert p["existing_outbound_rapport_policy"]["next_action"] == "RESEARCH"
        assert p["existing_outbound_rapport_policy"]["commercial_pricing_allowed"] is False
        assert p["outbound_authorized"] is False



def test_unavailable_exact_db_reader_does_not_overwrite_existing_revenue_snapshot(
    monkeypatch, tmp_path,
):
    from datetime import datetime, timezone
    import scripts.refresh_contractor_revenue_review as source

    original = cohort()
    frozen = tmp_path / "contractor_founder_review_latest.json"
    frozen.write_text('{"before":"preserved","outbound_authorized":false}')
    monkeypatch.setattr(source, "OUTPUT", frozen)
    monkeypatch.setattr(source, "run", lambda **kwargs: deepcopy(original))
    def fail_exact(_):
        raise PermissionError("UNAUTHORIZED_READER")
    monkeypatch.setattr(runner, "_canonical_exact_outbound_intents", fail_exact)
    with pytest.raises(PermissionError, match="UNAUTHORIZED_READER"):
        runner.refresh_existing_contractor_history(
            prior_contact_domains=set(), suppressed_emails=set()
        )
    assert json.loads(frozen.read_text()) == {
        "before": "preserved", "outbound_authorized": False,
    }
