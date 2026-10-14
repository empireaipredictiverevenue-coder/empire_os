"""Precisely three opt-outs are reconciled only through canonical DB controls."""
import json
from copy import deepcopy

import pytest

from scripts import reconcile_three_founder_optouts_20261014 as optouts

ROWS = {
    "07396f1e-f182-416d-b3de-3e5942cbbfa3": (
        "b14bd6c9-e801-4de0-9b6b-232142c6c1a2",
        "david@gastleylaw.com",
        "Re: David — opportunity intelligence for Gastley Law",
        "Opt out\nOn Mon, Sep 28 wrote:\n> If you'd rather not hear from me, reply opt out",
    ),
    "59be5458-bd1f-4676-a35f-7a3021292ba4": (
        "f992017f-628f-4253-aa19-14c0777585e1",
        "jason@ccdocs.com",
        "Re: Roofing / HVAC inbound call supply — current buy box?",
        "Hi, Thanks for reaching out. Please remove me from your mailing list.",
    ),
    "f044227f-25f8-4829-9378-04d0f6faab8a": (
        "1e7a4142-be64-40f1-8d3e-0cc39cea1653",
        "dieter@atlantarc.net", "opt out", "[provider body unavailable]",
    ),
}


def evidence_rows(*, classified=False, suppressed=False):
    return [
        {"reply_id": rid, "intent_id": iid,
         "sender": email, "recipient": email,
         "subject": subject, "body_text": body,
         "classification": "unsubscribe" if classified else "unclassified",
         "intent_status": "suppressed" if suppressed else "replied",
         "provider_id_present": True,
         "suppression_contact_type": "email" if suppressed else None}
        for rid, (iid, email, subject, body) in ROWS.items()
    ]


def test_validate_three_explicit_proofs_and_build_bounded_function_calls():
    result = optouts.validate(evidence_rows())
    assert result["proof_count"] == 3
    assert all(x["evidence_kind"].startswith("direct_") for x in result["rows"])
    sql = optouts._apply_sql(result)
    assert "SET LOCAL ROLE empire_reply_ingest" in sql
    assert "public.classify_outbound_reply" in sql
    assert sql.count("PERFORM public.classify_outbound_reply") == 3
    assert "FOR UPDATE OF reply, intent" in sql
    assert "COMMIT;" in sql
    assert "DROP TABLE" not in sql
    assert "send_with_gmail" not in sql
    assert all(row_id in sql for row_id in ROWS)


@pytest.mark.parametrize("bad_change", [
    lambda x: x.pop(),
    lambda x: x[0].update(recipient="someone-else@example.org"),
    lambda x: x[1].update(provider_id_present=False),
    lambda x: x[2].update(subject="Hello", body_text="[provider body unavailable]"),
    lambda x: x[0].update(classification="positive"),
    lambda x: x[0].update(suppression_contact_type="phone"),
    lambda x: x[1].update(intent_id="11111111-1111-4111-8111-111111111111"),
    lambda x: x[1].update(sender="other@example.org"),
])
def test_invalid_or_spoofed_proof_never_authorizes_suppression(bad_change):
    rows = evidence_rows()
    bad_change(rows)
    with pytest.raises(optouts.SuppressionHeld):
        optouts.validate(rows)


def test_nonroot_never_queries_database(monkeypatch):
    monkeypatch.setattr(optouts.os, "geteuid", lambda: 1000)
    with pytest.raises(optouts.SuppressionHeld, match="ROOT_ACCESS_REQUIRED"):
        optouts.reconcile(apply=False)


def test_explicit_apply_approval_required_before_db_access(monkeypatch, capsys):
    monkeypatch.setattr(optouts, "reconcile", lambda **kw: (_ for _ in ()).throw(
        AssertionError("DB_ACCESS_FORBIDDEN")))
    assert optouts.main(["--apply"]) == 2
    response = json.loads(capsys.readouterr().out)
    assert response["reason_code"] == "EXPLICIT_THREE_CONTACT_SUPPRESSION_APPROVAL_REQUIRED"
    assert response["mail_sent"] is False


def test_readonly_review_does_not_call_mutation(monkeypatch):
    monkeypatch.setattr(optouts.os, "geteuid", lambda: 0)
    monkeypatch.setattr(optouts, "_read", lambda: evidence_rows())
    monkeypatch.setattr(optouts, "_postgres_sql", lambda *args,**kw: (_ for _ in ()).throw(
        AssertionError("MUTATION_FORBIDDEN")))
    result = optouts.reconcile(apply=False)
    assert result["status"] == "READ_ONLY_REVIEW_VERIFIED"
    assert result["database_writes"] is False
    assert result["evidence_count"] == 3


def test_apply_calls_only_existing_classification_function_and_reads_back(monkeypatch):
    monkeypatch.setattr(optouts.os, "geteuid", lambda: 0)
    reads = iter([evidence_rows(), evidence_rows(classified=True, suppressed=True)])
    monkeypatch.setattr(optouts, "_read", lambda: next(reads))
    monkeypatch.setattr(optouts, "_dashboard_postcommit_check", lambda: True)
    writes = []
    monkeypatch.setattr(optouts, "_postgres_sql", lambda query,read_output: writes.append(query))
    outcome = optouts.reconcile(apply=True)
    assert len(writes) == 1
    assert outcome["status"] == "THREE_OPT_OUTS_CANONICALLY_SUPPRESSED"
    assert outcome["canonical_readback_verified"] is True
    assert outcome["email_sent"] is False
    assert outcome["database_writes"] is True


def test_preexisting_suppressions_do_not_repeat_mutation(monkeypatch):
    monkeypatch.setattr(optouts.os, "geteuid", lambda: 0)
    monkeypatch.setattr(optouts, "_read", lambda: evidence_rows(classified=True, suppressed=True))
    monkeypatch.setattr(optouts, "_dashboard_postcommit_check", lambda: True)
    monkeypatch.setattr(optouts, "_postgres_sql", lambda *a,**k: (_ for _ in ()).throw(AssertionError("REPEAT_MUTATION")))
    outcome = optouts.reconcile(apply=True)
    assert outcome["database_writes"] is False
    assert outcome["already_suppressed_count"] == 3


def test_unverified_postcommit_never_reports_completion(monkeypatch):
    monkeypatch.setattr(optouts.os, "geteuid", lambda: 0)
    reads = iter([evidence_rows(), evidence_rows()])
    monkeypatch.setattr(optouts, "_read", lambda: next(reads))
    monkeypatch.setattr(optouts, "_dashboard_postcommit_check", lambda: True)
    monkeypatch.setattr(optouts, "_postgres_sql", lambda *a,**k: None)
    with pytest.raises(optouts.SuppressionHeld, match="POSTCOMMIT"):
        optouts.reconcile(apply=True)

def test_dashboard_postcommit_checks_exact_three_threads_and_one_service_only(monkeypatch):
    from urllib.parse import urlsplit
    commands = []
    class ProcessResult:
        returncode = 0
    def fake_run(command, **kwargs):
        commands.append(command)
        return ProcessResult()
    monkeypatch.setattr(optouts.subprocess, "run", fake_run)
    opened = []
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, limit): return json.dumps({
            "classification": "unsubscribe",
            "suppressed": True,
            "execution_authority": "none",
        }).encode()
    class FakeOpener:
        def open(self, url, timeout):
            opened.append(url)
            return FakeResponse()
    monkeypatch.setattr(optouts, "build_opener", lambda *_: FakeOpener())
    assert optouts._dashboard_postcommit_check() is True
    assert commands == [["systemctl", "restart", "empire-founder-dashboard-api.service"]]
    assert len(opened) == 3
    for _, iid, _ in optouts.EVIDENCE:
        assert any(iid in url for url in opened)


def test_dashboard_bad_readback_never_claims_success(monkeypatch):
    class ProcessResult:
        returncode = 0
    monkeypatch.setattr(optouts.subprocess, "run", lambda *a,**k: ProcessResult())
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, limit): return json.dumps({
            "classification": "unknown", "suppressed": False,
            "execution_authority": "none",
        }).encode()
    class FakeOpener:
        def open(self, *a, **kw): return FakeResponse()
    monkeypatch.setattr(optouts, "build_opener", lambda *_: FakeOpener())
    assert optouts._dashboard_postcommit_check() is False
