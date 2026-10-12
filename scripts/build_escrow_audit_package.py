"""Build a deterministic, read-only review bundle for the EXISTING Empire BSC escrow.

Does not deploy, sign, use credentials, create wallets, grant roles, run a node,
write to EmpireDB, or produce a security-audit certification. It freezes the
exact compiler input/output and immutable reference map for independent review.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from typing import Any, Mapping

CONTRACT = "EmpireBscUsdtEscrow"
SOURCE_NAME = "project/contracts/EmpireBscUsdtEscrow.sol"
SOURCE_PATH = "contracts/escrow/contracts/EmpireBscUsdtEscrow.sol"
ARTIFACT_PATH = (
    "contracts/escrow/artifacts/contracts/"
    "EmpireBscUsdtEscrow.sol/EmpireBscUsdtEscrow.json"
)
PROJECT_RELATIVE = (
    SOURCE_PATH,
    "contracts/escrow/hardhat.config.js",
    "contracts/escrow/package.json",
    "contracts/escrow/package-lock.json",
    "contracts/escrow/test/EmpireBscUsdtEscrow.js",
    ARTIFACT_PATH,
)
REQUIRED_ARGS = (
    ("token_", "address"),
    ("beneficiary_", "address"),
    ("initialAdmin", "address"),
    ("requester", "address"),
    ("arbiter", "address"),
    ("pauser", "address"),
    ("decisionDelay_", "uint48"),
)
SOLC_VERSION = "0.8.34"
CHAIN_ID = 56
MAX_ASSET_BYTES = 12_000_000


class EscrowAuditBundleHold(ValueError):
    """Precondition error; no archive is released."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    p = root / relative
    if p.is_symlink() or not p.is_file():
        raise EscrowAuditBundleHold(f"missing or linked audit source: {relative}")
    blob = p.read_bytes()
    if not blob or len(blob) > MAX_ASSET_BYTES:
        raise EscrowAuditBundleHold(f"invalid audit source size: {relative}")
    return blob


def _json(raw: bytes, label: str) -> dict:
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise EscrowAuditBundleHold(f"malformed {label}") from exc
    if not isinstance(doc, dict):
        raise EscrowAuditBundleHold(f"invalid {label}")
    return doc


def _bytes(code: Any, label: str) -> bytes:
    if not isinstance(code, str) or not code.startswith("0x"):
        raise EscrowAuditBundleHold(f"invalid {label}")
    try:
        value = bytes.fromhex(code[2:])
    except ValueError as exc:
        raise EscrowAuditBundleHold(f"invalid {label}") from exc
    if len(value) < 100:
        raise EscrowAuditBundleHold(f"empty or truncated {label}")
    return value


def collect(root: Path, *, commit: str | None = None) -> tuple[dict, dict[str, bytes]]:
    """Freeze all reviewed inputs and exact non-linked creation/runtime bytes."""
    root = Path(root).resolve()
    files = {name: _read(root, name) for name in PROJECT_RELATIVE}
    artifact = _json(files[ARTIFACT_PATH], "Hardhat escrow artifact")
    if artifact.get("contractName") != CONTRACT or artifact.get("inputSourceName") != SOURCE_NAME:
        raise EscrowAuditBundleHold("artifact references wrong escrow contract")
    build_id = artifact.get("buildInfoId")
    if not isinstance(build_id, str) or not build_id.startswith("solc-0_8_34-") or "/" in build_id:
        raise EscrowAuditBundleHold("unrecognized escrow compiler build identifier")
    in_path = f"contracts/escrow/artifacts/build-info/{build_id}.json"
    out_path = f"contracts/escrow/artifacts/build-info/{build_id}.output.json"
    files[in_path] = _read(root, in_path)
    files[out_path] = _read(root, out_path)
    info = _json(files[in_path], "compiler input")
    output = _json(files[out_path], "compiler output")
    if (info.get("id") != build_id or output.get("id") != build_id
            or info.get("solcVersion") != SOLC_VERSION
            or info.get("compilerType") != "solc"):
        raise EscrowAuditBundleHold("compiler build provenance mismatch")
    compiler_input = info.get("input") or {}
    settings = compiler_input.get("settings") or {}
    optimizer = settings.get("optimizer") or {}
    if optimizer.get("enabled") is not True or optimizer.get("runs") != 200 or settings.get("evmVersion") != "cancun":
        raise EscrowAuditBundleHold("compiled artifact is not the approved optimizer/EVM profile")
    content = (compiler_input.get("sources") or {}).get(SOURCE_NAME, {}).get("content")
    if not isinstance(content, str) or content.encode() != files[SOURCE_PATH]:
        raise EscrowAuditBundleHold("source file differs from compiled Solidity input")
    compiled = ((output.get("output") or {}).get("contracts") or {}).get(SOURCE_NAME, {}).get(CONTRACT)
    if not isinstance(compiled, dict):
        raise EscrowAuditBundleHold("compiled contract missing from compiler output")
    constructor = next((v for v in artifact.get("abi", []) if v.get("type") == "constructor"), None)
    if constructor is None:
        raise EscrowAuditBundleHold("missing constructor ABI")
    args = tuple((x.get("name"), x.get("type")) for x in constructor.get("inputs", ()))
    if args != REQUIRED_ARGS:
        raise EscrowAuditBundleHold("constructor identity/role signature changed")
    artifact_create = _bytes(artifact.get("bytecode"), "creation bytecode")
    artifact_runtime = _bytes(artifact.get("deployedBytecode"), "template runtime bytecode")
    try:
        build_create = bytes.fromhex(compiled["evm"]["bytecode"]["object"])
        build_runtime = bytes.fromhex(compiled["evm"]["deployedBytecode"]["object"])
        immutable = compiled["evm"]["deployedBytecode"]["immutableReferences"]
    except (ValueError, KeyError, TypeError) as exc:
        raise EscrowAuditBundleHold("compiled output missing verified bytecode") from exc
    if artifact_create != build_create or artifact_runtime != build_runtime:
        raise EscrowAuditBundleHold("artifact bytecode differs from compiler output")
    if not immutable or not isinstance(immutable, dict):
        raise EscrowAuditBundleHold("missing immutable constructor slots")
    if artifact.get("immutableReferences") != immutable:
        raise EscrowAuditBundleHold("constructor immutable slot map differs from compiler output")
    # The runtime template still contains constructor-specific placeholder bytes.
    # Never claim its SHA as the expected deployed runtime code hash.
    if commit is None:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                check=True, text=True, timeout=5
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise EscrowAuditBundleHold("repository commit unavailable") from exc
    if not isinstance(commit, str) or len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise EscrowAuditBundleHold("invalid source commit provenance")
    manifest = {
        "schema_version": "empire.bsc-escrow-reproducible-review-bundle.v1",
        "purpose": "OFFLINE_SECURITY_AND_DEPLOYMENT_REVIEW_NOT_CERTIFICATION",
        "source_commit": commit,
        "contract": CONTRACT,
        "chain_id_for_future_deployment": CHAIN_ID,
        "canonical_usdt_bsc_contract": "0x55d398326f99059ff775485246999027b3197955",
        "build_info_id": build_id,
        "solidity_version": info["solcVersion"],
        "solidity_long_version": info.get("solcLongVersion"),
        "optimizer_enabled": True,
        "optimizer_runs": 200,
        "evm_version": "cancun",
        "constructor_abi": [{"name": x, "type": typ} for x, typ in REQUIRED_ARGS],
        "creation_bytecode_sha256": sha(artifact_create),
        "creation_bytecode_length": len(artifact_create),
        "runtime_template_sha256_NOT_AN_ONCHAIN_FINGERPRINT": sha(artifact_runtime),
        "runtime_template_length": len(artifact_runtime),
        "immutable_constructor_references": immutable,
        "source_files": {name: {"sha256": sha(data), "bytes": len(data)}
                         for name, data in sorted(files.items())},
        "deployment_transaction_verified": False,
        "onchain_runtime_bytecode_sha256_verified": False,
        "onchain_roles_and_escrow_beneficiary_verified": False,
        "treasury_wallet_ownership_verified": False,
        "external_security_audit_verified": False,
        "financial_operators_provisioned": False,
        "payment_collection_activated": False,
        "funds_moved": False,
        "release_authority": "none",
    }
    return manifest, files


def _tar_item(name: str, blob: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(blob)
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info, blob


def build_bundle(root: Path, output: Path, *, commit: str | None = None) -> dict:
    """Atomic create-only output; reproducible archive bytes at same commit."""
    manifest, files = collect(root, commit=commit)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise EscrowAuditBundleHold("existing output cannot be overwritten")
    if not output.parent.is_dir():
        raise EscrowAuditBundleHold("parent output directory must exist")
    entries = dict(files)
    entries["ESCROW_REVIEW_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode()
    payload = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=payload, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, blob in sorted(entries.items()):
                info, content = _tar_item(name, blob)
                tar.addfile(info, io.BytesIO(content))
    file_data = payload.getvalue()
    fd = output.open("xb")
    try:
        with fd:
            fd.write(file_data)
            fd.flush()
        output.chmod(0o600)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    report = dict(manifest)
    report.update({
        "offline_review_package_path": str(output),
        "offline_review_package_sha256": sha(file_data),
        "offline_review_package_bytes": len(file_data),
        "file_count_in_package": len(entries),
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args()
    result = build_bundle(opts.root, opts.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
