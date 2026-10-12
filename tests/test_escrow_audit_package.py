"""Reproducible, immutable, no-secrets escrow review bundle tests."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts import build_escrow_audit_package as audit

ROOT = Path(__file__).resolve().parents[1]
FIXED_COMMIT = "c" * 40


@pytest.fixture()
def available_compiler_inputs():
    try:
        manifest, files = audit.collect(ROOT, commit=FIXED_COMMIT)
    except audit.EscrowAuditBundleHold as exc:
        if str(exc).startswith("missing or linked audit source: contracts/escrow/artifacts/"):
            pytest.skip("first run npm run compile to materialize existing offline artifact")
        raise
    return manifest, files


def test_rebuilt_contract_has_exact_approved_constructor_and_solc_profile(available_compiler_inputs):
    manifest, files = available_compiler_inputs
    assert manifest["schema_version"].endswith(".v1")
    assert manifest["chain_id_for_future_deployment"] == 56
    assert manifest["solidity_version"] == "0.8.34"
    assert manifest["optimizer_enabled"] is True
    assert manifest["optimizer_runs"] == 200
    assert manifest["evm_version"] == "cancun"
    assert tuple((p["name"], p["type"]) for p in manifest["constructor_abi"]) == audit.REQUIRED_ARGS
    assert manifest["creation_bytecode_length"] > 8000
    assert len(manifest["immutable_constructor_references"]) == 3
    assert len(files) == 8
    assert manifest["deployment_transaction_verified"] is False
    assert manifest["onchain_runtime_bytecode_sha256_verified"] is False
    assert manifest["treasury_wallet_ownership_verified"] is False
    assert manifest["payment_collection_activated"] is False
    assert manifest["funds_moved"] is False
    assert "runtime_template_sha256_NOT_AN_ONCHAIN_FINGERPRINT" in manifest


def test_archive_deterministic_content_digest_and_excludes_credentials(tmp_path, available_compiler_inputs):
    _, files = available_compiler_inputs
    out1 = tmp_path / "A.tar.gz"
    out2 = tmp_path / "B.tar.gz"
    a = audit.build_bundle(ROOT, out1, commit=FIXED_COMMIT)
    b = audit.build_bundle(ROOT, out2, commit=FIXED_COMMIT)
    assert out1.read_bytes() == out2.read_bytes()
    assert a["offline_review_package_sha256"] == b["offline_review_package_sha256"]
    assert a["file_count_in_package"] == len(files) + 1
    assert out1.stat().st_mode & 0o777 == 0o600
    with tarfile.open(out1, "r:gz") as archive:
        names = archive.getnames()
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)
        assert len(names) == len(set(names))
        manifest = json.load(archive.extractfile("ESCROW_REVIEW_MANIFEST.json"))
        assert manifest["source_commit"] == FIXED_COMMIT
        assert manifest["source_files"][audit.SOURCE_PATH]["sha256"] == audit.sha(
            archive.extractfile(audit.SOURCE_PATH).read()
        )
        for name in names:
            assert "private_key" not in name
            assert ".env" not in name
            assert "mnemonic" not in name
            assert "node_modules" not in name
            assert archive.getmember(name).mtime == 0
            assert archive.getmember(name).uid == 0
        assert manifest["external_security_audit_verified"] is False
        assert manifest["release_authority"] == "none"


def test_bundle_never_overwrites_existing_artifact(tmp_path, available_compiler_inputs):
    path = tmp_path / "existing.tar.gz"
    path.write_text("do not overwrite")
    with pytest.raises(audit.EscrowAuditBundleHold, match="existing output"):
        audit.build_bundle(ROOT, path, commit=FIXED_COMMIT)
    assert path.read_text() == "do not overwrite"


def test_source_mismatch_compiler_output_fails_closed(monkeypatch, available_compiler_inputs):
    original = audit._read
    def wrong_source(root, relative):
        data = original(root, relative)
        if relative == audit.SOURCE_PATH:
            return data.replace(b"EmpireBscUsdtEscrow", b"OtherBscUsdtEscrow", 1)
        return data
    monkeypatch.setattr(audit, "_read", wrong_source)
    with pytest.raises(audit.EscrowAuditBundleHold, match="source file differs"):
        audit.collect(ROOT, commit=FIXED_COMMIT)


def test_runtime_bytecode_tamper_fails_closed(monkeypatch, available_compiler_inputs):
    original = audit._read
    def corrupted_artifact(root, relative):
        raw = original(root, relative)
        if relative == audit.ARTIFACT_PATH:
            value = json.loads(raw)
            bytecode = value["deployedBytecode"]
            value["deployedBytecode"] = bytecode[:-2] + ("00" if bytecode[-2:] != "00" else "ff")
            return json.dumps(value).encode()
        return raw
    monkeypatch.setattr(audit, "_read", corrupted_artifact)
    with pytest.raises(audit.EscrowAuditBundleHold, match="bytecode differs"):
        audit.collect(ROOT, commit=FIXED_COMMIT)


def test_constructor_param_drift_fails_closed(monkeypatch, available_compiler_inputs):
    original = audit._read
    def altered(root, relative):
        raw = original(root, relative)
        if relative == audit.ARTIFACT_PATH:
            value = json.loads(raw)
            constructor = next(x for x in value["abi"] if x["type"]=="constructor")
            constructor["inputs"][1]["name"] = "newBeneficiaryWithoutApproval"
            return json.dumps(value).encode()
        return raw
    monkeypatch.setattr(audit, "_read", altered)
    with pytest.raises(audit.EscrowAuditBundleHold, match="constructor identity"):
        audit.collect(ROOT, commit=FIXED_COMMIT)


def test_optimizer_or_evm_version_changed_fails_closed(monkeypatch, available_compiler_inputs):
    original = audit._read
    def altered(root, relative):
        raw = original(root, relative)
        if relative.endswith("build-info/" + available_compiler_inputs[0]["build_info_id"] + ".json"):
            val = json.loads(raw)
            val["input"]["settings"]["optimizer"]["runs"]=1
            return json.dumps(val).encode()
        return raw
    monkeypatch.setattr(audit, "_read", altered)
    with pytest.raises(audit.EscrowAuditBundleHold, match="optimizer/EVM"):
        audit.collect(ROOT, commit=FIXED_COMMIT)


def test_invalid_source_commit_and_missing_compilation_stop_before_archive(tmp_path,available_compiler_inputs):
    for bad_commit in ("", "deadbeef", "x"*40):
        with pytest.raises(audit.EscrowAuditBundleHold, match="commit"):
            audit.build_bundle(ROOT, tmp_path / "denied.tar.gz", commit=bad_commit)
    assert not (tmp_path / "denied.tar.gz").exists()


def test_tar_member_reproducibility_is_not_an_external_security_audit(available_compiler_inputs):
    manifest, _ = available_compiler_inputs
    assert manifest["purpose"] == "OFFLINE_SECURITY_AND_DEPLOYMENT_REVIEW_NOT_CERTIFICATION"
    assert manifest["external_security_audit_verified"] is False
    assert manifest["onchain_roles_and_escrow_beneficiary_verified"] is False
    assert manifest["financial_operators_provisioned"] is False
    assert manifest["payment_collection_activated"] is False
