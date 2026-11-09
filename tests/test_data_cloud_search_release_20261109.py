"""Offline release receipt and exact public entrypoint assembly tests."""
import hashlib
import json
import runpy
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import predictive_cloud_search_release as release
from tests.test_predictive_cloud_route_assembly_20261107 import components

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def synthetic_release_module_mapping(monkeypatch, tmp_path):
    # Synthetic pinned package files model the exact modules that would be
    # loaded by the original gateway during this isolated release rehearsal.
    monkeypatch.setattr(
        release, "_imported_module_path",
        lambda qualified: (tmp_path / (qualified.replace(".", "/") + ".py")).resolve(),
    )


def receipt_tree(tmp_path):
    for name in release.REQUIRED_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic pinned executable")
    receipt = dict(
        scope=release.SCOPE, owner_actor_id="owner", owner_tenant_id="tenant",
        source_id="empire_search_fabric_public",
        verified_requirements={k: True for k in release.SEARCH_PILOT_REQUIREMENTS},
        files={n: hashlib.sha256((tmp_path / n).read_bytes()).hexdigest()
               for n in release.REQUIRED_FILES},
    )
    return receipt


def load(tmp_path, receipt, **overrides):
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    return release.load_search_release(
        path, expected_sha256=overrides.get("digest", hashlib.sha256(path.read_bytes()).hexdigest()),
        release=tmp_path, owner=overrides.get("owner", "owner"), tenant="tenant",
    )


def test_receipt_idempotent_read_only_and_tenant_source_bound(tmp_path):
    receipt = receipt_tree(tmp_path)
    evidence, request, output = load(tmp_path, receipt)
    assert load(tmp_path, receipt)[0] == evidence
    assert request("tenant", receipt["source_id"], "roofing", 2)
    assert not request("other", receipt["source_id"], "roofing", 2)
    assert not request("tenant", "paid_provider", "roofing", 2)
    assert not request("tenant", receipt["source_id"], "roofing", True)
    assert output("tenant", receipt["source_id"], {"source_id": receipt["source_id"]})
    assert not output("other", receipt["source_id"], receipt)
    assert not output("tenant", receipt["source_id"], {"source_id": "other"})


@pytest.mark.parametrize("mutation", ["hash", "missing", "escape", "symlink", "writable", "scope", "owner", "evidence", "digest"])
def test_invalid_receipt_or_executable_fails_closed(tmp_path, mutation):
    receipt = receipt_tree(tmp_path)
    name = next(iter(release.REQUIRED_FILES))
    overrides = {}
    if mutation == "hash":
        (tmp_path / name).write_text("drift")
    elif mutation == "missing":
        del receipt["files"][name]
    elif mutation == "escape":
        receipt["files"]["../outside"] = "0" * 64
    elif mutation == "symlink":
        target = tmp_path / name
        target.unlink()
        target.symlink_to(tmp_path / "receipt.json")
    elif mutation == "writable":
        (tmp_path / name).chmod(0o666)
    elif mutation == "scope":
        receipt["scope"] = "commercial"
    elif mutation == "owner":
        overrides["owner"] = "other"
    elif mutation == "evidence":
        receipt["verified_requirements"]["production_meter_write_functions_verified"] = 1
    else:
        overrides["digest"] = "0" * 64
    with pytest.raises(RuntimeError, match="not_verified"):
        load(tmp_path, receipt, **overrides)


def test_pinned_files_reject_a_different_preloaded_python_module(monkeypatch, tmp_path):
    receipt = receipt_tree(tmp_path)
    monkeypatch.setattr(
        release, "_imported_module_path",
        lambda qualified: Path("/srv/empire_os/old_imported_module.py"),
    )
    with pytest.raises(RuntimeError, match="first_party_search_release_not_verified"):
        load(tmp_path, receipt)


@pytest.mark.parametrize("search_enabled", [False, True])
def test_original_entrypoint_preserves_upstream_app_and_issuer(monkeypatch, tmp_path, components, search_enabled):
    """Execute actual owner source with only protected resources substituted.

    Real route assembler and verifier; synthetic DB/config/upstream gateway.
    No production module import side effects, credentials or network.
    """
    import empire_os
    from empire_os.predictive_cloud_customer_api import gateway_candidate_entrypoint as candidate_owner
    verifier, state, candidate, evidence, signed_session = components
    host = FastAPI()

    @host.get("/unrelated-live-route")
    def unrelated():
        return {"preserved": True}

    host.state.crm_issuer_marker = object()
    marker = host.state.crm_issuer_marker
    old_route = host.routes[-1]
    upstream = types.ModuleType("linkedin_browser_ui_entrypoint")
    upstream.app = host
    monkeypatch.setitem(sys.modules, "linkedin_browser_ui_entrypoint", upstream)
    import empire_os.predictive_cloud_founder_session as sessions
    import empire_os.revenue_crm_signed_auth as crm
    monkeypatch.setattr(crm, "EmpireDbCrmMembershipReader", lambda *a: object())
    monkeypatch.setattr(candidate_owner, "create_gateway_candidate_app", lambda **kw: candidate())
    monkeypatch.setattr(release, "load_search_release", lambda *a, **kw: (
        {k: True for k in release.SEARCH_PILOT_REQUIREMENTS}, lambda *a: True, lambda *a: True))
    monkeypatch.setenv("EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE", "FOUNDER_APPROVED_READ_ONLY_USAGE_20261107")
    monkeypatch.delenv("EMPIRE_DATA_CLOUD_FOUNDER_SEARCH_RELEASE", raising=False)
    if search_enabled:
        monkeypatch.setenv("EMPIRE_DATA_CLOUD_FOUNDER_SEARCH_RELEASE", release.FLAG)
    frozen = tmp_path / "frozen"
    (frozen / "empire_os").mkdir(parents=True)
    config = tmp_path / "runtime.json"
    passfile = tmp_path / "synthetic-passfile"
    passfile.touch()
    config.write_text(json.dumps(dict(
        scope="FOUNDER_ONLY_USAGE_NO_PROVIDERS", release_version=1,
        owner_actor_id="owner", owner_tenant_id="tenant", crm_membership_dsn="dbname=synthetic",
        crm_membership_passfile=str(passfile), meter_password="synthetic",
        data_signing_key_id="synthetic", data_signing_public_key_hex="00" * 32,
    )))
    config.chmod(0o600)
    (tmp_path / "RELEASE_EVIDENCE.json").write_text(json.dumps(dict(
        source_sql_sha256="d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393",
        mode="FOUNDER_ONLY_USAGE_NO_PROVIDERS", verified_requirements={k: True for k in release.SEARCH_PILOT_REQUIREMENTS},
    )))
    source = (ROOT / "scripts/data_cloud_public_entrypoint_20261107.py").read_text()
    # Substitute only the test constructor call, not the shared verifier class
    # itself: the original assembler uses an exact isinstance authority gate.
    source = source.replace("verifier = DataCloudPublicVerifier(",
                            "verifier = _verified_test_public_verifier(")
    source = source.replace('Path("/opt/empire-ai/data-cloud-founder-pilot-20261107")', repr(frozen))
    source = source.replace('Path("/var/lib/empire-data-cloud-founder-pilot/runtime.json")', repr(config))
    source = source.replace('Path("/srv/empire_os/empire_os")', repr(Path(empire_os.__file__).resolve().parent))
    # repr(Path) uses PosixPath; bind it without touching production paths.
    namespace = {"PosixPath": Path,
                 "_verified_test_public_verifier": lambda **kw: verifier}
    original_path = list(empire_os.__path__)
    try:
        exec(compile(source, "original_public_entrypoint", "exec"), namespace)
    finally:
        empire_os.__path__[:] = original_path
    assert namespace["app"] is host
    assert old_route in host.routes and host.state.crm_issuer_marker is marker
    with TestClient(host) as client:
        assert client.get("/unrelated-live-route").json() == {"preserved": True}
        assert client.get("/v1/data/usage").status_code == 401
        assert client.post("/v1/data/search", json={"query": "roofing"}).status_code == (401 if search_enabled else 404)
        assert client.post("/v1/data/site-audits").status_code == 404
