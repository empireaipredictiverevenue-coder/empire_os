"""Verify the exact GetTradesmen Gmail bounce write without contacting EmpireDB."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.record_publisher_gmail_hard_bounce import (
    BOUNCE_MESSAGE_ID,
    EvidenceHold,
    REASON,
    RECIPIENT,
    SENT_MESSAGE_ID,
    SOURCE,
    main,
    record_bounce,
    verify_proof,
)

PROOF = "docs/commercial/PUBLISHER_RECRUITMENT_GMAIL_SEND_EVIDENCE_20261010.json"


def proof():
    with open(PROOF, encoding="utf-8") as stream:
        return json.load(stream)


def save(tmp_path, payload):
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_exact_source_proof_and_read_only_cli(tmp_path, capsys):
    assert len(verify_proof(save(tmp_path, proof()))) == 64
    assert main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DRY_RUN_PROOF_VERIFIED"
    assert result["database_write"] is False
    assert result["recipient"] == RECIPIENT


@pytest.mark.parametrize("change", [
    lambda p: p.update(source_mailbox="attacker@example.org"),
    lambda p: p.update(confirmed_hard_bounce_count=0),
    lambda p: p["messages"][2].update(bounce_gmail_message_id="fake"),
    lambda p: p["messages"][2].update(recipient="someone@example.org"),
    lambda p: p["messages"][2].update(retry_authorized=True),
    lambda p: p["messages"][2].update(gmail_message_id="different"),
    lambda p: p["messages"][0].update(recipient=RECIPIENT),
])
def test_forged_or_conflicting_evidence_fails_closed(tmp_path, change):
    d = deepcopy(proof())
    change(d)
    with pytest.raises(EvidenceHold):
        verify_proof(save(tmp_path, d))


def test_apply_flag_requires_explicit_approval(capsys):
    assert main(["--apply"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "HELD_NO_CONFIRMED_SUPPRESSION"


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.results = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        if "INSERT INTO public.outbound_suppressions" in sql:
            assert params == (RECIPIENT, REASON, SOURCE)
            assert "ON CONFLICT" in sql
            self.db["insert_count"] += 1
            if self.db["record"] is None:
                self.db["record"] = (RECIPIENT, "email", REASON, SOURCE)
        elif "SELECT normalized_contact,contact_type,reason,source" in sql:
            assert params == (RECIPIENT,)
            self.results = [self.db["record"]] if self.db["record"] else []
        else:
            assert sql.startswith("SET ")
    def fetchall(self): return self.results


class FakeConn:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return FakeCursor(self.db)


def connect(db):
    return lambda dsn: FakeConn(db)


def test_atomic_only_exact_email_insert_and_reverify():
    db = {"record": None, "insert_count": 0}
    assert record_bounce("TEST_ONLY_NO_CONNECTION", connect(db)) == "INSERTED"
    assert db == {"record": (RECIPIENT, "email", REASON, SOURCE), "insert_count": 1}
    assert record_bounce("TEST_ONLY_NO_CONNECTION", connect(db)) == "ALREADY_SUPPRESSED"
    assert db["insert_count"] == 1


def test_prior_suppression_not_overwritten():
    db = {"record": (RECIPIENT, "email", "opt_out", "existing"), "insert_count": 0}
    assert record_bounce("TEST_ONLY_NO_CONNECTION", connect(db)) == "ALREADY_SUPPRESSED"
    assert db["insert_count"] == 0


def test_conflicting_existing_contact_type_fails():
    db = {"record": (RECIPIENT, "domain", "invalid", "existing"), "insert_count": 0}
    with pytest.raises(EvidenceHold, match="CONFLICTING_EXISTING_CONTACT_TYPE"):
        record_bounce("TEST_ONLY_NO_CONNECTION", connect(db))
    assert db["insert_count"] == 0
