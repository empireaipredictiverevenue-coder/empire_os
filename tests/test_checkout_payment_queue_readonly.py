from datetime import datetime, timedelta, timezone
from uuid import UUID

from scripts import checkout_payment_queue_readonly as q


def row(status, expires):
    now=datetime(2026,10,13,tzinfo=timezone.utc)
    return (UUID("11111111-1111-4111-8111-111111111111"),
            UUID("22222222-2222-4222-8222-222222222222"),
            "199.00",status,now-timedelta(minutes=2),expires)


def test_empty_queue_no_fake_revenue():
    out=q.summarize([], now=datetime.now(timezone.utc))
    assert out["results"]==[]
    assert out["pending_review_count"]==0
    assert out["payment_executed"] is False
    assert out["customer_contact_data_disclosed"] is False


def test_pending_is_reviewer_action_not_send_instruction():
    now=datetime(2026,10,13,tzinfo=timezone.utc)
    out=q.summarize([row("pending",now+timedelta(hours=1))],now=now)
    assert out["pending_review_count"]==1
    assert out["approved_instruction_delivery_count"]==0
    assert out["results"][0]["next_step"]=="REVIEW_WITH_DEDICATED_OPERATOR"
    assert "payer_address" not in out["results"][0]
    assert "email" not in out["results"][0]


def test_approved_can_be_delivered_but_not_marked_paid():
    now=datetime(2026,10,13,tzinfo=timezone.utc)
    out=q.summarize([row("approved",now+timedelta(hours=1))],now=now)
    assert out["approved_instruction_delivery_count"]==1
    assert out["results"][0]["next_step"]=="SEND_APPROVED_INSTRUCTIONS_VIA_VERIFIED_BUYER_CHANNEL"
    assert out["actual_revenue"] is False
    assert out["payment_approved"] is False


def test_expired_request_never_suggests_payment():
    now=datetime(2026,10,13,tzinfo=timezone.utc)
    out=q.summarize([row("approved",now-timedelta(seconds=1))],now=now)
    assert out["approved_instruction_delivery_count"]==0
    assert out["results"][0]["next_step"]=="EXPIRED_HOLD_NO_PAYMENT_INSTRUCTIONS"


def test_unprivileged_execution_is_blocked(monkeypatch,capsys):
    import pwd
    monkeypatch.setattr(q.os,"geteuid",lambda:1000)
    monkeypatch.setattr(q.pwd,"getpwnam",lambda name: type("User",(),{"pw_uid":999})())
    assert q.main([])==2
    assert "BLOCKED_POSTGRES_OS_ID_REQUIRED" in capsys.readouterr().out


def test_unknown_arguments_never_connect(capsys):
    assert q.main(["--apply"])==2
    assert "BLOCKED_READONLY_ARGS_REQUIRED" in capsys.readouterr().out


def test_sql_is_bounded_and_cannot_write():
    assert "LIMIT %s" in q.SQL
    assert "SELECT id, fulfilment_order_id" in q.SQL
    assert "payer_address" not in q.SQL
    assert "buyer_id" not in q.SQL
    assert all(word not in q.SQL.upper() for word in ("INSERT ","UPDATE ","DELETE ","DROP ","ALTER "))
