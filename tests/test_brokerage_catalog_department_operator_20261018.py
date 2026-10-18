"""Existing department worker consumes private founder-safe brokerage reviews."""
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import json
import pytest

from empire_os.data_brokerage_product_catalog import (
    build_data_brokerage_product_catalog, validate_internal_brokerage_catalog,
)
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os import source_intelligence_handoff as router
from scripts import preview_data_brokerage_products as runner

NOW=datetime(2026,10,18,10,15,tzinfo=timezone.utc)


def _catalog():
    return build_data_brokerage_product_catalog(assessed_at=NOW)


def test_catalog_integrity_verifies_and_forgeries_fail_closed():
    d=_catalog()
    assert validate_internal_brokerage_catalog(d) is True
    for k,v in (("third_party_resale_authorized",True),
                ("product_publication_authorized",True),
                ("verified_payment_count",1),
                ("source_cost_budget_gbp",1),
                ("evidence_scope_sha256","a"*64)):
        changed={**d,k:v}
        assert not validate_internal_brokerage_catalog(changed)
    import copy
    changed=copy.deepcopy(d)
    changed["products"][0]["buyer_verified"]=True
    assert not validate_internal_brokerage_catalog(changed)
    changed=copy.deepcopy(d)
    changed["products"][0]["source_evidence_summary"]["rights_cleared"]=True
    assert not validate_internal_brokerage_catalog(changed)


def test_private_catalog_receipt_routes_only_existing_strategy_department(
    tmp_path,monkeypatch,
):
    import empire_os.source_intelligence_handoff as module
    monkeypatch.setattr(module,"CANONICAL_ROOT",tmp_path)
    monkeypatch.setattr(module,"inspect_free_commoncrawl_dataset", lambda: None)
    saved=tmp_path/"runtime/data_brokerage/internal_product_catalog_latest.json"
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps(_catalog()))
    now=NOW
    d=router.build_source_intelligence_handoffs(tmp_path,now=now)
    assert d["lane_count"]==6  # Five base lanes + validated brokerage
    by={r["lane"]:r for r in d["routes"]}
    assert by["data_brokerage"]["department"]=="strategy"
    assert by["data_brokerage"]["counts"]["internal_product_count"]==4
    assert by["data_brokerage"]["counts"]["approved_customer_data_exports"]==0
    assert "third_party_raw_record_resale_not_authorized" in by["data_brokerage"]["blockers"]
    first=module.dispatch_source_intelligence_handoffs(
        tmp_path,now=now,max_jobs=5,allow_noncanonical_test=True)
    second=module.dispatch_source_intelligence_handoffs(
        tmp_path,now=now.replace(minute=20),max_jobs=5,allow_noncanonical_test=True)
    again=module.dispatch_source_intelligence_handoffs(
        tmp_path,now=now.replace(minute=30),max_jobs=5,allow_noncanonical_test=True)
    assert first["handoffs_enqueued"]==5
    assert second["handoffs_enqueued"]==1
    assert again["handoffs_enqueued"]==0
    assert again["handoffs_unchanged"]==6
    assert DepartmentWorkQueue(tmp_path).counts()["ready"]==6
    source_packet=json.loads((tmp_path/module.SNAPSHOT).read_text())
    row=next(r for r in source_packet["routes"] if r["lane"]=="data_brokerage")
    review=module.deliver_source_intelligence_review(
        tmp_path,lane="data_brokerage",
        fingerprint=row["evidence_fingerprint"],department="strategy")
    data=review["data_brokerage_internal_review"]
    assert data["product_count"]==4
    assert data["customer_distribution_authorized"] is False
    assert data["actual_revenue_verified"] is False
    assert all(p["buyer_verified"] is False for p in data["products"])
    assert all(p["customer_delivery_enabled"] is False for p in data["products"])
    assert review["outbound_sent"] is False
    assert review["semantic_model_review_performed"] is False


def test_invalid_brokerage_file_does_not_poison_other_source_queues(
    tmp_path,monkeypatch,
):
    monkeypatch.setattr(router,"CANONICAL_ROOT",tmp_path)
    monkeypatch.setattr(router,"inspect_free_commoncrawl_dataset", lambda: None)
    target=tmp_path/"runtime/data_brokerage/internal_product_catalog_latest.json"
    target.parent.mkdir(parents=True)
    forged=_catalog()
    forged["verified_payment_count"]=99
    target.write_text(json.dumps(forged))
    d=router.build_source_intelligence_handoffs(tmp_path,now=NOW)
    assert d["lane_count"]==5
    assert not any(r["lane"]=="data_brokerage" for r in d["routes"])


def test_catalog_cli_noncanonical_does_not_write(tmp_path,capsys):
    ret=runner.main(["--read-only"],repo_root=tmp_path)
    assert ret==0
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="PRIVATE_INTERNAL_BROKERAGE_REVIEW_READY"
    assert d["preview_materialized_private"] is False
    assert d["source_custody_state"]=="CANONICAL_CUSTODY_NOT_INSPECTED"
    assert not list(tmp_path.iterdir())


def test_catalog_cli_requires_protected_inspection_and_canonical_location(tmp_path,capsys):
    ret=runner.main(["--read-only","--materialize-private"],
                    repo_root=tmp_path)
    assert ret==2
    assert json.loads(capsys.readouterr().out)["status"]=="HOLD"
    assert not list(tmp_path.iterdir())


def test_catalog_cli_rejects_oversized_or_malformed_stdin_without_logging(
    tmp_path,capsys,
):
    for content in ("PRIVATE_PII_NEVER_ECHO", "X"*300_000):
        ret=runner.main(["--read-only","--inspection-stdin"],
                        repo_root=tmp_path,stdin=StringIO(content))
        assert ret==2
        output=capsys.readouterr().out
        assert "PRIVATE_PII_NEVER_ECHO" not in output
        assert json.loads(output)["status"]=="HOLD"
    assert not list(tmp_path.iterdir())


def test_scoped_private_writer_writes_exact_source_safe_catalog(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,"CANONICAL_ROOT",tmp_path)
    d=_catalog()
    runner._write_review(tmp_path,d)
    p=tmp_path/runner.PRIVATE_REPORT
    assert p.exists()
    assert p.stat().st_mode & 0o777==0o600
    saved=json.loads(p.read_text())
    assert validate_internal_brokerage_catalog(saved)
    assert len(saved["products"])==4
    assert saved["third_party_resale_authorized"] is False
    assert saved["verified_payment_count"]==0



def test_provenance_cli_founder_declaration_readonly_and_no_media_modification(
    tmp_path,capsys,
):
    asset=tmp_path/"founder_visual.png"
    asset.write_bytes(b"ORIGINAL_USER_SUPPLIED_CONTENT")
    original=asset.read_bytes()
    ret=runner.main(
        ["--read-only",
         "--founder-asset-file",str(asset),
         "--founder-asset-id","founder-original-visual-v1",
         "--founder-origin","FOUNDER_DIRECTED_AI_ASSISTED",
         "--founder-ai-assistance","AI_ASSISTED_DECLARED",
         "--founder-ownership-declared"],
        repo_root=tmp_path,
    )
    assert ret==0
    result=json.loads(capsys.readouterr().out)
    assert result["founder_owned_assets_registered"]==1
    assert len(result["founder_asset_integrity_sha256"])==64
    assert result["founder_origin_independently_verified"] is False
    assert result["watermark_removal_attempted"] is False
    assert result["preview_materialized_private"] is False
    assert asset.read_bytes()==original
    assert not (tmp_path/"runtime").exists()


def test_provenance_cli_fails_closed_without_founder_origin_declaration(
    tmp_path,capsys,
):
    file=tmp_path/"founder_visual.png"
    file.write_bytes(b"PRIVATE_FOUNDER_ORIGINAL")
    ret=runner.main(
        ["--read-only","--founder-asset-file",str(file),
         "--founder-asset-id","founder-original-visual-v1",
         "--founder-origin","FOUNDER_ORIGINAL",
         "--founder-ai-assistance","UNKNOWN"],
        repo_root=tmp_path,
    )
    assert ret==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HOLD"
    assert "PRIVATE_FOUNDER" not in json.dumps(report)
    assert not (tmp_path/"runtime").exists()


def test_private_founder_receipt_is_hash_only_and_immutable(
    tmp_path,monkeypatch,
):
    monkeypatch.setattr(runner,"CANONICAL_ROOT",tmp_path)
    source=tmp_path/"asset.png"
    source.write_bytes(b"ORIGINAL_USER_SUPPLIED_CONTENT")
    from empire_os.founder_asset_provenance import build_founder_asset_receipt
    manifest=build_founder_asset_receipt(
        source,
        asset_id="founder-origin-asset-v1",
        origin_class="FOUNDER_DIRECTED_AI_ASSISTED",
        ai_assistance="AI_ASSISTED_DECLARED",
        founder_ownership_declared=True,
        third_party_components_declared=None,
    )
    runner._write_founder_receipt(tmp_path,manifest)
    target=tmp_path/runner.ASSET_MANIFEST_DIR/"founder-origin-asset-v1.json"
    assert target.exists()
    assert target.stat().st_mode & 0o777==0o600
    saved=json.loads(target.read_text())
    assert saved["file_sha256"]==manifest["file_sha256"]
    assert saved["public_release_authorized"] is False
    assert saved["production_asset_modified"] is False
    runner._write_founder_receipt(tmp_path,manifest)
    source.write_bytes(b"REPLACED_ASSET_VERSION")
    next_manifest=build_founder_asset_receipt(
        source,
        asset_id="founder-origin-asset-v1",
        origin_class="FOUNDER_DIRECTED_AI_ASSISTED",
        ai_assistance="AI_ASSISTED_DECLARED",
        founder_ownership_declared=True,
        third_party_components_declared=None,
    )
    with pytest.raises(ValueError,match="immutable"):
        runner._write_founder_receipt(tmp_path,next_manifest)
    assert json.loads(target.read_text())==saved
