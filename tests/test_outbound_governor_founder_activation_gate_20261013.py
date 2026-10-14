"""Additional independent founder execution gate for Gmail-capable governor."""
from __future__ import annotations

import json

from scripts import outbound_governor_worker as worker


def test_timer_execute_cannot_send_even_with_provider_and_auto_flags(monkeypatch,capsys):
    for key,value in {
        "EMPIRE_OUTBOUND_AUTO_SEND":"true",
        "EMPIRE_OUTBOUND_AUTO_APPROVE":"true",
        "EMPIRE_OUTBOUND_GOVERNOR_MODE":"GUARDED_EXECUTE",
    }.items():
        monkeypatch.setenv(key,value)
    # The relevant regression: provider may become ready in a later release.
    monkeypatch.setattr(worker,"_provider_ready",lambda:True)
    observed=[]
    def sender(method,args):
        observed.append(method)
        if method=="list_outbound_governor_work":
            return [{"intent_id":"11111111-1111-4111-8111-111111111111",
                     "status":"approved","updated_at":"2026-10-13T00:00:00Z"}]
        if method=="get_outbound_intent_review":
            return {"decision":"review","intent_id":args["p_intent_id"],
                    "status":"approved","actual_revenue":False,
                    "channel":"email","recipient":"test-buyer@example.com",
                    "subject":"Test","expires_at":"2027-01-01T00:00:00Z",
                    "body_text":"Hello. Reply opt out. 68 Wentbridge Road, Bolton, BL1 2QR, UK"}
        if method=="get_outbound_governor_context":
            return {"suppressed":False,"review_ready":True,"outreach_ready":True,
                    "bound_to_decision_maker":True,"contact_source":"official_site",
                    "contact_confidence":.95,"company_score":90}
        raise AssertionError("Forbidden mutation: "+method)
    monkeypatch.setattr(worker,"_sender_rpc",lambda:sender)
    monkeypatch.setattr(worker,"_approver_rpc",lambda: (_ for _ in ()).throw(
        AssertionError("No approver in timer mode")))
    monkeypatch.setattr(worker,"execute_governor_decision",lambda *args,**kwargs: (_ for _ in ()).throw(
        AssertionError("No send or approval")))
    rc=worker.main(["--mode","GUARDED_EXECUTE","--execute","--limit","1"])
    result=json.loads(capsys.readouterr().out)
    assert rc==0
    assert result["execution_requested"] is True
    assert result["founder_activation_present"] is False
    assert result["execute"] is False
    assert result["mode"]=="OBSERVE"
    assert result["results"][0]["evaluation"]["mutation_authorized"] is False
    assert all(x in ("list_outbound_governor_work","get_outbound_intent_review",
                     "get_outbound_governor_context") for x in observed)


def test_explicit_activation_does_not_bypass_closed_provider(monkeypatch,capsys):
    monkeypatch.setenv("EMPIRE_OUTBOUND_AUTO_SEND","true")
    monkeypatch.setenv("EMPIRE_OUTBOUND_AUTO_APPROVE","true")
    monkeypatch.setattr(worker,"_provider_ready",lambda:False)
    monkeypatch.setattr(worker,"_sender_rpc",lambda:lambda method,args: [])
    rc=worker.main(["--mode","GUARDED_EXECUTE","--execute","--founder-activate","--limit","1"])
    result=json.loads(capsys.readouterr().out)
    assert rc==0
    assert result["founder_activation_present"] is True
    assert result["owned_mailbox_gate"]=="CLOSED"
    assert result["execute"] is False
    assert result["mode"]=="OBSERVE"
