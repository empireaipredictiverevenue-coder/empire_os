"""Customer template -> safe missing/invalid -> source-scoped review."""
import json
from datetime import datetime,timezone

import pytest

from empire_os.predictive_commercial_intake_readiness import (
    inspect_commercial_intake_draft,REQUIRED_TO_PLAN,
)
from scripts.print_predictive_commercial_intake_template_20261020 import (
    commercial_intake_template,
)
from scripts import review_predictive_commercial_requirements_20261020 as cli

NOW=datetime(2026,10,20,15,tzinfo=timezone.utc)

def fixed(monkeypatch):
    class Clock:
        @staticmethod
        def now(zone):return NOW
    monkeypatch.setattr(cli,"datetime",Clock)


def test_blank_template_is_incomplete_not_error_or_secret_leak():
    r=inspect_commercial_intake_draft(commercial_intake_template())
    assert r["status"]=="COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS"
    assert r["missing_required_planning_fields"]==list(REQUIRED_TO_PLAN)
    assert r["valid_customer_order_authenticated"] is False
    assert r["source_inventory_reconciled"] is False
    assert r["database_writes"] is False


def test_template_file_review_is_helpful_and_does_not_modify_existing_file(
    tmp_path,monkeypatch,capsys,
):
    fixed(monkeypatch)
    p=tmp_path/"company_request.json"
    source=json.dumps(commercial_intake_template(),sort_keys=True)
    p.write_text(source)
    monkeypatch.setattr("sys.argv",["operator","--read-only",
        "--repo-root",str(tmp_path),"--requirement-intake",str(p)])
    assert cli.main()==0
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS"
    assert out["commercial_intake_readiness"]["missing_required_planning_fields"]==[
        "country","state","city","industry","currency","requested_qualified_leads"]
    assert out["owner_handoffs_prepared"]==0
    assert out["source_owner_reports_read"] is False
    assert p.read_text()==source


def test_only_planning_required_values_gate_the_hypothetical_research_review():
    x=commercial_intake_template()
    x.update(country="US",state="AZ",city="Phoenix",industry="hvac",
             currency="USD",requested_qualified_leads=30)
    result=inspect_commercial_intake_draft(x)
    assert result["status"]=="COMMERCIAL_INTAKE_PLANNING_FIELDS_SUPPLIED"
    assert result["valid_customer_order_authenticated"] is False


def test_unknown_or_missing_schema_key_fail_closed_with_field_names_not_payload():
    x=commercial_intake_template()
    x["unknown_customer_secret"]="private"
    x.pop("delivery_deadline")
    r=inspect_commercial_intake_draft(x)
    assert r["status"]=="COMMERCIAL_INTAKE_INVALID_STRUCTURE"
    assert r["missing_schema_field_count"]==1
    assert r["unknown_schema_field_count"]==1
    assert "private" not in json.dumps(r)
    assert "unknown_customer_secret" not in json.dumps(r)


@pytest.mark.parametrize("text",["{not JSON", "null", "[]"])
def test_invalid_json_or_non_object_returns_no_traceback(tmp_path,monkeypatch,capsys,text):
    fixed(monkeypatch)
    p=tmp_path/"broken.json"
    p.write_text(text)
    monkeypatch.setattr("sys.argv",["operator","--read-only",
        "--repo-root",str(tmp_path),"--requirement-intake",str(p)])
    assert cli.main()==2
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="COMMERCIAL_INTAKE_FILE_INVALID"
    assert out["database_writes"] is False


def test_unsupported_country_and_fake_approval_cannot_be_promoted(tmp_path,monkeypatch,capsys):
    fixed(monkeypatch)
    x=commercial_intake_template()
    x.update(country="QQ",state="ZZ",city="Nowhere",industry="other",
             currency="USD",requested_qualified_leads=13)
    p=tmp_path/"bad.json";p.write_text(json.dumps(x))
    monkeypatch.setattr("sys.argv",["operator","--read-only",
        "--repo-root",str(tmp_path),"--requirement-intake",str(p)])
    assert cli.main()==2
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="COMMERCIAL_INTAKE_INVALID_VALUES"
    assert out["owner_handoffs_dispatched"]==0
    assert out["database_writes"] is False


def test_symlinked_owner_file_not_followed(tmp_path,monkeypatch,capsys):
    fixed(monkeypatch)
    target=tmp_path/"draft.json";target.write_text(json.dumps(commercial_intake_template()))
    link=tmp_path/"linked.json";link.symlink_to(target)
    monkeypatch.setattr("sys.argv",["operator","--read-only",
        "--repo-root",str(tmp_path),"--requirement-intake",str(link)])
    assert cli.main()==2
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="COMMERCIAL_INTAKE_FILE_INVALID"
