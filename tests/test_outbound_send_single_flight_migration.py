from pathlib import Path

SQL_PATH = Path(
    "migrations/empiredb/032_outbound_send_single_flight.sql"
)


def _sql() -> str:
    return " ".join(SQL_PATH.read_text().lower().split())


def test_single_flight_states_are_canonical():
    sql = _sql()
    assert "'sending'" in sql
    assert "'reconciliation_required'" in sql
    assert "outbound_intents_status_check" in sql


def test_claim_atomically_moves_approved_to_sending():
    sql = _sql()
    assert "for update" in sql
    assert "status = 'sending'" in sql
    assert "and status = 'approved'" in sql
    assert "outbound intent already claimed" in sql

    transition = sql.index("status = 'sending'")
    attempt = sql.index("'send_attempt'")
    assert transition < attempt


def test_sent_requires_prior_claim():
    sql = _sql()
    assert (
        "r.status not in ('sending', 'sent')"
        in sql
    )
    assert "claimed outbound intent required" in sql


def test_unknown_provider_outcome_has_fail_closed_state():
    sql = _sql()
    assert "'reconciliation_required'" in sql
    assert "sending intent required" in sql


def test_migration_contains_no_provider_send():
    sql = _sql()
    assert "api.resend.com" not in sql
    assert "/api/v1/send/message" not in sql
    assert "x-server-api-key" not in sql
