#!/usr/bin/env python3
"""Prepare exact reviewed candidate from protected ROOT helper, no service switch.

The generated candidate contains the original root-owned helper release,
one self-contained kernel peer policy, one zero-authority identity adapter,
and only a bounded helper socket-listener delta. No production writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ORIGINAL = Path("/opt/empire-ai/privileged-helper/releases/20261015-custody-audit-v5")
REPO = Path(__file__).resolve().parents[1]
DEST = Path("/home/ubuntu/empire_releases/root_helper_agent_identity_candidate_20261022")
PINNED_HASH = "3d2d66c17c09900864eef3ca6776af0456269c655479c8d615c6762c566ec239"
FILES = {
    "90-root-owned-helper.conf",
    "CHECKSUMS.sha256",
    "empire_os/__init__.py",
    "empire_os/data_cloud_runtime_health.py",
    "empire_os/ops_privileged_helper.py",
}
NEW = {
    "empire_os/agent_peer_identity.py",
    "empire_os/agent_identity_root_adapter.py",
}

ORIGINAL_SERVE = '''    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o660)
        server.listen(8)
        while True:
            conn, _ = server.accept()
            with conn:
                _serve_connection(conn, allowed_uid=allowed_uid)'''

NEW_SERVE = '''    identity_path = socket_path.with_name(IDENTITY_SOCKET_BASENAME)
    identity_path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server, \\
         socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as identity_server:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o660)
        server.listen(8)
        identity_server.bind(str(identity_path))
        os.chmod(identity_path, 0o660)
        identity_server.listen(8)
        while True:
            readable, _, _ = select.select((server, identity_server), (), ())
            for ready in readable:
                conn, _ = ready.accept()
                with conn:
                    if ready is identity_server:
                        serve_identity_preflight(conn)
                    else:
                        _serve_connection(conn, allowed_uid=allowed_uid)'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_candidate() -> dict[str, bytes]:
    if (
        not ORIGINAL.is_dir()
        or ORIGINAL.is_symlink()
        or ORIGINAL.stat().st_uid != 0
        or digest(ORIGINAL / "empire_os/ops_privileged_helper.py") != PINNED_HASH
    ):
        raise ValueError("protected_root_helper_release_not_pinned")
    originals = {str(p.relative_to(ORIGINAL)) for p in ORIGINAL.rglob("*") if p.is_file()}
    if originals != FILES or any(p.is_symlink() for p in ORIGINAL.rglob("*")):
        raise ValueError("unexpected_original_root_helper_contents")
    content = {
        rel: (ORIGINAL / rel).read_bytes()
        for rel in sorted(FILES)
    }
    original = content["empire_os/ops_privileged_helper.py"].decode()
    if original.count(ORIGINAL_SERVE) != 1:
        raise ValueError("original_helper_server_contract_changed")
    import_anchor = "import socket\n"
    if original.count(import_anchor) != 1:
        raise ValueError("original_helper_import_contract_changed")
    patched = original.replace(
        import_anchor,
        'import select\nimport socket\n'
        'from empire_os.agent_identity_root_adapter import '
        'IDENTITY_SOCKET_BASENAME, serve_identity_preflight\n',
        1,
    ).replace(ORIGINAL_SERVE, NEW_SERVE, 1)
    content["empire_os/ops_privileged_helper.py"] = patched.encode()
    for rel in sorted(NEW):
        content[rel] = (REPO / rel).read_bytes()
    # The original checksum file described the protected *prior* release.
    # Rebuild a self-consistent manifest, never falsely advertise stale
    # checksums for the updated handler and two new read-only modules.
    lines = [
        f"{hashlib.sha256(data).hexdigest()}  {rel}"
        for rel, data in sorted(content.items())
        if rel != "CHECKSUMS.sha256"
    ]
    content["CHECKSUMS.sha256"] = (chr(10).join(lines) + chr(10)).encode()
    return content


def validate_candidate(root: Path, required: dict[str, bytes]) -> dict:
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual != set(required):
        raise ValueError("candidate_files_not_exact")
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("candidate_symlink_forbidden")
    for rel, expected in required.items():
        if (root / rel).read_bytes() != expected:
            raise ValueError(f"candidate_file_changed:{rel}")
    return {
        "status": "PINNED_ROOT_HELPER_IDENTITY_READONLY_CANDIDATE_VERIFIED",
        "original_pinned_helper_sha256": PINNED_HASH,
        "candidate_helper_sha256": digest(root / "empire_os/ops_privileged_helper.py"),
        "kernel_peer_policy_sha256": digest(root / "empire_os/agent_peer_identity.py"),
        "adapter_sha256": digest(root / "empire_os/agent_identity_root_adapter.py"),
        "original_files_preserved_except_helper": True,
        "agent_modules_added": 2,
        "original_root_service_modified": False,
        "identity_socket_running": False,
        "persistent_keys_issued": False,
        "collaboration_activated": False,
    }


def main() -> int:
    if sys.argv[1:] not in (["--stage"], ["--verify"]):
        print("STAGING_HELD_EXACT_FLAG_REQUIRED")
        return 2
    required = render_candidate()
    if sys.argv[1:] == ["--stage"]:
        if DEST.exists() or DEST.is_symlink():
            raise ValueError("stage_destination_exists_reuse_verify_only")
        os.makedirs(DEST, mode=0o700)
        for rel, data in required.items():
            target = DEST / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
    result = validate_candidate(DEST, required)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
