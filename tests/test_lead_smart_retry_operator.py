"""The operator never enables the campaign during preview or out-of-window runs."""
from datetime import datetime, timezone
import json
import pytest
from scripts import activate_lead_smart_supervised_retry as op
from empire_os.lead_smart_site_handoff import CAMPAIGN, NUMBER, SCHEMA


def control():
    return {
        "campaign_id":CAMPAIGN,"tracking_number":NUMBER,
        "schema_version":SCHEMA,"enabled":False,
        "starts_at":"2026-10-19T15:00:00+00:00",
        "ends_at":"2026-10-19T17:00:00+00:00",
        "monitoring_owner":"Phillip Livesley",
        "stop_method":"atomic_site_handoff_gate",
        "max_site_handoffs":5,
        "founder_authority_ref":
            "docs/evidence/lead_smart_founder_launch_intent_20261011.json",
    }


def test_tuesday_retry_window_is_explicit_and_bounded():
    a,b=op.window("2026-10-20T10:00",15)
    assert a.isoformat()=="2026-10-20T15:00:00+00:00"
    assert b.isoformat()=="2026-10-20T15:15:00+00:00"
    assert op.revised_control(control(),a,b,5)["enabled"] is False


@pytest.mark.parametrize("time,minutes", [
    ("2026-10-20T07:59",15),
    ("2026-10-20T17:50",20),
    ("2026-10-17T10:00",15),
    ("2026-10-20T10:00",21),
    ("2026-10-20T10:00",9),
])
def test_unsafe_time_or_duration_rejected(time,minutes):
    with pytest.raises(ValueError):
        op.window(time,minutes)


def test_disabled_preview_does_not_modify_control_or_install_timer(tmp_path,monkeypatch):
    cfg=tmp_path/"approved_control.json"
    cfg.write_text(json.dumps(control()))
    before=cfg.read_bytes()
    monkeypatch.setattr(op,"CONFIG",cfg)
    monkeypatch.setattr(op,"refresh_coverage",lambda:
        (_ for _ in ()).throw(AssertionError("preview made network calls")))
    monkeypatch.setattr(op.subprocess,"run",lambda *a,**kw:
        (_ for _ in ()).throw(AssertionError("preview touched systemd")))
    result=op.run("2026-10-20T10:00",15,5,apply=False)
    assert result["status"]=="REVIEW_ONLY"
    assert result["site_calls_enabled"] is False
    assert cfg.read_bytes()==before


def test_apply_outside_selected_window_leaves_original_disabled(tmp_path,monkeypatch):
    cfg=tmp_path/"approved_control.json"
    cfg.write_text(json.dumps(control()))
    before=cfg.read_bytes()
    monkeypatch.setattr(op,"CONFIG",cfg)
    with pytest.raises(RuntimeError,match="outside selected launch minute"):
        op.run("2026-10-20T10:00",15,5,apply=True)
    assert cfg.read_bytes()==before


def test_timer_is_installed_before_site_call_switch(monkeypatch,tmp_path):
    from datetime import timedelta
    real_datetime=datetime
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls,tz=None):
            value=real_datetime(2026,10,20,15,0,10,tzinfo=timezone.utc)
            return value if tz is None else value.astimezone(tz)
    monkeypatch.setattr(op,"datetime",FrozenDateTime)
    cfg=tmp_path/"approved_control.json"
    ledger=tmp_path/"site_handoffs.json"
    cfg.write_text(json.dumps(control()))
    monkeypatch.setattr(op,"CONFIG",cfg)
    monkeypatch.setattr(op,"LEDGER",ledger)
    monkeypatch.setattr(op,"refresh_coverage",lambda:None)
    calls=[]
    def simulate(command,**kwargs):
        calls.append(command)
        if command[:3]==["sudo","-n","systemd-run"]:
            assert json.loads(cfg.read_text())["enabled"] is False
            assert "--property=WorkingDirectory=/srv/empire_os" in command
            assert "--on-active=" in " ".join(command)
        return type("Result",(),{"returncode":0})()
    monkeypatch.setattr(op.subprocess,"run",simulate)
    def readiness():
        active=json.loads(cfg.read_text())["enabled"]
        return {"blockers":[] if active else ["pilot_stop_verified"],
                "launch_ready":active}
    monkeypatch.setattr(op,"compute_live_launch_readiness",readiness)
    result=op.run("2026-10-20T10:00",15,5,apply=True)
    assert result["status"]=="LIVE_SITE_HANDOFF_ENABLED"
    assert result["site_calls_enabled"] is True
    assert json.loads(cfg.read_text())["enabled"] is True
    assert calls[0][:3]==["sudo","-n","systemd-run"]
    assert calls[1][:3]==["systemctl","is-active","--quiet"]
