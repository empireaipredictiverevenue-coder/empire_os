"""Safety tests for the bounded publisher cohort Gmail/EmpireDB history preflight."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/buyer_network_intelligence/publisher_cohort_20261010_preflight.py"
PROOF = ROOT / "docs/commercial/PUBLISHER_RECRUITMENT_GMAIL_SEND_EVIDENCE_20261010.json"


def load():
    spec = importlib.util.spec_from_file_location("publisher_readonly_preflight", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def set_proof(monkeypatch, module, tmp_path, proof):
    directory = tmp_path / "docs" / "commercial"
    directory.mkdir(parents=True)
    (directory / "PUBLISHER_RECRUITMENT_GMAIL_SEND_EVIDENCE_20261010.json").write_text(
        json.dumps(proof), encoding="utf-8"
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)


def test_four_gmail_sends_count_as_prior_contacts_without_db_intents(
    monkeypatch, tmp_path, capsys
):
    module = load()
    set_proof(monkeypatch, module, tmp_path, json.loads(PROOF.read_text()))
    monkeypatch.setenv("EMPIREDB_DSN", "TEST_NO_CONNECTION")
    monkeypatch.setattr(module, "_canonical_contact_history", lambda: (set(), set(), set()))
    monkeypatch.setattr(module, "_canonical_exact_outbound_intents", lambda _: set())
    assert module.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["cohort_count"] == 8
    assert result["exact_prior_intent_matches"] == 0
    assert result["gmail_prior_send_count"] == 4
    assert result["contact_already_attempted_count"] == 4
    assert result["gmail_hard_bounce_holds"] == 1
    rows = {row["email"]: row for row in result["rows"]}
    assert rows["gettradesmen@gmail.com"]["gmail_hard_bounce_hold"] is True
    assert rows["gettradesmen@gmail.com"]["send_authorized"] is False
    assert rows["contact@roofpitch.net"]["contact_already_attempted"] is True
    assert rows["hello@roofingcalculatorusa.com"]["contact_already_attempted"] is False
    assert result["outbound_authorized"] is False


@pytest.mark.parametrize("kind", ["duplicate_recipient", "invalid_bounce", "conflicting_total"])
def test_conflicting_gmail_history_fails_closed(monkeypatch, tmp_path, capsys, kind):
    module = load()
    proof = json.loads(PROOF.read_text())
    if kind == "duplicate_recipient":
        proof["messages"][1]["recipient"] = proof["messages"][0]["recipient"]
    elif kind == "invalid_bounce":
        proof["messages"][2]["retry_authorized"] = True
    else:
        proof["submitted_to_gmail_count"] = 3
    set_proof(monkeypatch, module, tmp_path, proof)
    monkeypatch.setenv("EMPIREDB_DSN", "TEST_NO_CONNECTION")
    monkeypatch.setattr(module, "_canonical_contact_history", lambda: (set(), set(), set()))
    monkeypatch.setattr(module, "_canonical_exact_outbound_intents", lambda _: set())
    assert module.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["canonical_read_completed"] is False
    assert result["outbound_authorized"] is False
    assert result["state"] == "HOLD_CANONICAL_HISTORY_UNAVAILABLE"

def test_canonical_prior_intent_and_gmail_send_are_deduplicated(monkeypatch, tmp_path, capsys):
    module = load()
    set_proof(monkeypatch, module, tmp_path, json.loads(PROOF.read_text()))
    monkeypatch.setenv("EMPIREDB_DSN", "TEST_NO_CONNECTION")
    monkeypatch.setattr(module, "_canonical_contact_history", lambda: (set(), set(), set()))
    monkeypatch.setattr(module, "_canonical_exact_outbound_intents",
                        lambda _: {"contact@roofpitch.net", "contact@getbuilding.co.uk"})
    assert module.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["exact_prior_intent_matches"] == 2
    assert result["gmail_prior_send_count"] == 4
    assert result["contact_already_attempted_count"] == 5
    assert not result["individual_recipient_suppression_cleared"]
    assert not result["outbound_authorized"]
