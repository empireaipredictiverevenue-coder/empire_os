"""Original archive staging: preserve source bytes except canonical import changes."""
from __future__ import annotations
import hashlib, importlib.util, zipfile
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/stage_original_customer_api_20261107.py"
spec=importlib.util.spec_from_file_location("stage_customer",SCRIPT)
stage_customer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_customer)

SOURCES={
 "durable_store.py": "from dataclasses import dataclass\n",
 "private_api.py": "from fastapi import FastAPI\n",
 "durable_api.py": (
 "from gateway_attestation import verify_gateway_attestation\n"
 "from durable_store import DurablePilotStore, ActiveTenant, AdmissionError\n"
 "from private_api import AuditRequest, SearchRequest, parse_safe_http_url\n"),
 "empiredb_metering_adapter.py":
 "from durable_store import ActiveTenant, AdmissionError\n",
 "gateway_candidate_entrypoint.py":
 "from durable_api import create_metered_private_app\n"
 "from empiredb_metering_adapter import EmpireDbMeteringStore\n",
}

def archive(tmp_path,duplicate=False):
    path=tmp_path/"original.zip"
    with zipfile.ZipFile(path,"w") as z:
        for name,content in SOURCES.items():
            z.writestr("original/"+name,content)
        if duplicate:
            z.writestr("original/durable_api.py",SOURCES["durable_api.py"])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return path,digest

def test_wrong_archive_hash_rejected_before_writing(tmp_path):
    path,digest=archive(tmp_path)
    with pytest.raises(ValueError,match="wrong original"):
        stage_customer.stage(path,tmp_path/"source","0"*64)
    assert not (tmp_path/"source").exists()

def test_canonical_import_rewrite_only(tmp_path,monkeypatch):
    path,digest=archive(tmp_path)
    monkeypatch.setattr(stage_customer,"PINNED_ARCHIVE_SHA256",digest)
    out=tmp_path/"source"
    receipt=stage_customer.stage(path,out,digest)
    assert receipt["only_import_rewrites"] is True
    assert len(receipt["original_source_sha256"])==5
    assert receipt["original_source_sha256"]["private_api.py"]==receipt["converted_sha256"]["private_api.py"]
    src=(out/"durable_api.py").read_text()
    assert "from empire_os.predictive_cloud_gateway_attestation import verify_gateway_attestation" in src
    assert "from .durable_store import" in src
    assert "from .private_api import" in src
    with pytest.raises(ValueError,match="destination exists"):
        stage_customer.stage(path,out,digest)

def test_duplicate_archive_member_fails_closed(tmp_path,monkeypatch):
    path,digest=archive(tmp_path,duplicate=True)
    monkeypatch.setattr(stage_customer,"PINNED_ARCHIVE_SHA256",digest)
    with pytest.raises(ValueError,match="duplicate zip entries"):
        stage_customer.stage(path,tmp_path/"source",digest)
    assert not (tmp_path/"source").exists()
