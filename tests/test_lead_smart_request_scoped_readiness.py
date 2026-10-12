"""Request-scoped launch truth; no repeating one-shot materialization timer."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts import materialize_lead_smart_launch_readiness as release
from empire_os import lead_smart_pilot_call_api as handoff

APPROVED_HASH = "faea59c0d8c6d510db8af876a53af439eac41e294f8d348e20576c75bd43cccb"


def test_deployed_roofing_hash_stays_verified_and_any_drift_holds(tmp_path, monkeypatch):
    root=tmp_path/"source"
    for name in ("templates/lead_smart/roofing/page.tsx",
                 "apps/empire-public-site/src/app/roofing/page.tsx"):
        f=root/name
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_bytes(Path(name).read_bytes())
        assert hashlib.sha256(f.read_bytes()).hexdigest()==APPROVED_HASH
    site=tmp_path/"site"
    site.mkdir()
    html=site/"roofing.html"
    html.write_bytes(b"approved-html")
    monkeypatch.setattr(release, "APPROVED_ROOFING_HTML_SHA256",
                        hashlib.sha256(html.read_bytes()).hexdigest())
    report={"approved":True, "source_ref":"gmail:1a12bc009d04fcc9",
            "reviewed_source_sha256":APPROVED_HASH}
    assert release.approved_live_publication(report,repo_root=root,site_root=site)
    html.write_bytes(b"modified-html")
    assert not release.approved_live_publication(report,repo_root=root,site_root=site)
    html.unlink()
    html.symlink_to(Path("/etc/hosts"))
    assert not release.approved_live_publication(report,repo_root=root,site_root=site)


def test_request_live_readiness_recomputed_from_primary_evidence_not_old_snapshot(
        tmp_path, monkeypatch):
    now=datetime(2026,10,12,15,20,tzinfo=timezone.utc)
    root=tmp_path/"runtime"
    def save(relative,data):
        target=root/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(data))
    save("ringba/tracking_verification/latest.json",{
        "state":"VERIFIED","tracking_verified":True,
        "verified_at":now.isoformat(),"source_observed_at":now.isoformat()
    })
    save("coverage/activation/latest.json",{
        "zip_targeting_gate_verified":True,
        "zip_coverage_activation_verified":True,"source_fresh_for_targeting":True,
        "source_observed_at":now.isoformat(),
        "verified_freshness":{"source_newest_last_updated":now.isoformat()}
    })
    save("ringba/routing_observation/latest.json",{
        "routing_runtime_verified":True,"observed_at":now.isoformat()
    })
    # A materialized READY/phone-enabled record is NOT proof and is ignored.
    save("launch_readiness/latest.json",{
        "schema_version":"empire.lead_smart.launch_readiness.v1",
        "mode":"READY","launch_ready":True,"call_cta_enabled":True
    })
    monkeypatch.setattr(release,"effective_legal_release_verified",lambda:False)
    monkeypatch.setattr(release,"verified_site_handoff_control",lambda:False)
    monkeypatch.setattr(release,"approved_live_publication",
                        lambda *_args,**_kw:True)
    result=release.compute_live_launch_readiness(
        evidence_root=root,
        repo_root=Path(__file__).resolve().parents[1],
        now=now,
    )
    assert result["mode"]=="PREACTIVATION"
    assert result["call_cta_enabled"] is False
    assert result["operating_hours"]["evaluated_at"]==now.isoformat()
    assert result["gates"]["tracking_verified"] is True
    assert result["gates"]["routing_runtime_verified"] is True
    assert result["gates"]["landing_publication_authorized"] is True
    assert "legal_release_verified" in result["blockers"]
    assert "pilot_stop_verified" in result["blockers"]


def test_public_call_preview_uses_fresh_builder_and_fails_on_missing_evidence(
        monkeypatch):
    monkeypatch.setattr(handoff,"_released_privacy_terms",lambda:True)
    monkeypatch.setattr(handoff,"_in_current_coverage",lambda _zip:True)
    monkeypatch.setattr(
        handoff,"compute_live_launch_readiness",
        lambda:{"schema_version":"empire.lead_smart.launch_readiness.v1",
                "mode":"PREACTIVATION","launch_ready":False,
                "gates":{"legal_release_verified":False}}
    )
    # A stale readiness file must not be read or passed along to permit logic.
    monkeypatch.setattr(handoff,"_json",lambda _p: (_ for _ in ()).throw(
        AssertionError("call API must never depend on cached readiness file")))
    assert handoff.call_available("10001") is False
    monkeypatch.setattr(handoff,"compute_live_launch_readiness",
                        lambda: (_ for _ in ()).throw(FileNotFoundError()))
    assert handoff.call_available("10001") is False
