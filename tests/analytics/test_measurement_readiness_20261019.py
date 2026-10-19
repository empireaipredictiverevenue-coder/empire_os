"""Read-only re-use of real EmpireOS Tag Intelligence status, no traffic claims."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import pytest

from empire_os.analytics.measurement_readiness import (
    SCHEMA, SOURCE_SCHEMA, review_snapshot, review_existing_monitor,
)

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)


def snapshot(*, consent=None, ga4=None, gtm=None):
    return {
        "schema_version":SOURCE_SCHEMA,"mode":"OBSERVE",
        "execution_authority":"none",
        "measurement_platform_write":False,"automatic_tag_mutation":False,
        "generated_at":(NOW-timedelta(hours=2)).isoformat(),
        "targets":[{
            "url":"https://empire-ai.co.uk","available":True,
            "measurement_tags":{
                "ga4_measurement_ids":ga4 if ga4 is not None else [],
                "gtm_container_ids":gtm if gtm is not None else [],
                "google_tag_ids":[],
                "consent_mode_enabled":consent,
                "hidden_user_data":"test-email@fake.invalid",
            },
            "limitations":["static_markup_observation_only","google_hit_delivery_not_observed"],
            "analysis":{"issues":[]},
        }],
    }


def test_real_static_snapshot_is_not_a_visitor_analytics_success():
    d=review_snapshot(snapshot(),now=NOW)
    assert d["schema_version"]==SCHEMA
    assert d["status"]=="STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD"
    assert d["static_homepage_observation_verified"] is True
    assert d["static_ga4_tag_declared"] is False
    assert d["static_consent_configuration"]=="NOT_VERIFIED_FROM_STATIC_OBSERVATION"
    for field in ("tag_firing_or_delivery_verified",
                  "lawful_website_analytics_consent_verified","website_sessions_verified",
                  "first_party_collector_activation_verified","crm_attribution_verified",
                  "realised_revenue_verified","database_writes","outbound_sent",
                  "public_site_changed"):
        assert d[field] is False
    assert "test-email@fake.invalid" not in json.dumps(d)
    assert "measurement_tags" not in json.dumps(d)
    assert "google_tag_ids" not in json.dumps(d)


def test_configured_tag_ids_never_leave_readiness_report_or_prove_delivery():
    d=review_snapshot(snapshot(consent=True,ga4=["G-TESTSECRETKEY"],
                               gtm=["GTM-ANOTHERSECRET"]),now=NOW)
    assert d["static_ga4_tag_declared"] is True
    assert d["static_gtm_tag_declared"] is True
    assert d["static_consent_configuration"]=="CONFIG_FLAG_PRESENT_NOT_LEGAL_PROOF"
    assert d["lawful_website_analytics_consent_verified"] is False
    assert d["tag_firing_or_delivery_verified"] is False
    assert "TESTSECRETKEY" not in json.dumps(d)
    assert "ANOTHERSECRET" not in json.dumps(d)


@pytest.mark.parametrize("modify",[
    lambda s:s.update(schema_version="untrusted"),
    lambda s:s.update(mode="ACTIVE"),
    lambda s:s.update(execution_authority="APPROVED"),
    lambda s:s.update(measurement_platform_write=True),
    lambda s:s.update(automatic_tag_mutation=True),
    lambda s:s.update(generated_at=""),
    lambda s:s.update(generated_at=(NOW-timedelta(days=5)).isoformat()),
    lambda s:s.update(generated_at=(NOW+timedelta(days=2)).isoformat()),
    lambda s:s["targets"].clear(),
    lambda s:s["targets"][0].update(url="https://some-other-domain.example"),
    lambda s:s["targets"][0].update(available=False),
    lambda s:s["targets"][0].update(measurement_tags=None),
    lambda s:s["targets"][0].update(limitations=[]),
])
def test_invalid_source_monitor_or_stale_observation_held(modify):
    s=snapshot();modify(s)
    d=review_snapshot(s,now=NOW)
    assert d["status"]=="HELD_TAG_SOURCE_UNVERIFIED"
    assert d["static_homepage_observation_verified"] is False
    assert d["website_sessions_verified"] is False
    assert d["execution_authority"]=="NONE"


def test_duplicate_empire_target_fails_closed():
    s=snapshot()
    s["targets"].append(dict(s["targets"][0]))
    d=review_snapshot(s,now=NOW)
    assert d["status"]=="HELD_TAG_SOURCE_UNVERIFIED"


def test_exact_snapshot_file_only(tmp_path):
    p=tmp_path/"observed.json"
    p.write_text(json.dumps(snapshot()))
    d=review_existing_monitor(p,now=NOW)
    assert d["static_homepage_observation_verified"] is True


def test_symlink_rejected(tmp_path):
    actual=tmp_path/"real.json"
    actual.write_text(json.dumps(snapshot()))
    link=tmp_path/"alias.json"
    link.symlink_to(actual)
    d=review_existing_monitor(link,now=NOW)
    assert d["status"]=="HELD_TAG_SOURCE_UNVERIFIED"


def test_secret_string_not_leaked_from_broken_file(tmp_path):
    p=tmp_path/"broken.json"
    p.write_text('{"secret":"sensitive-string"}garbled')
    d=review_existing_monitor(p,now=NOW)
    assert d["status"]=="HELD_TAG_SOURCE_UNVERIFIED"
    assert "sensitive-string" not in json.dumps(d)


def test_oversize_file_rejected(tmp_path):
    p=tmp_path/"large.json"
    p.write_bytes(b"x"*300000)
    d=review_existing_monitor(p,now=NOW)
    assert d["status"]=="HELD_TAG_SOURCE_UNVERIFIED"


def test_only_static_source_says_it_saw_a_tag_not_that_hits_were_delivered():
    s=snapshot()
    s["targets"][0]["measurement_tags"]["observed_events"]=["purchase"]
    d=review_snapshot(s,now=NOW)
    assert d["tag_firing_or_delivery_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert "purchase" not in json.dumps(d)
