"""Only source-pinned, authenticated review route may overlay live Smart CRM.

No import of live systemd application or production DB is needed for
these checks; genuine owner-process startup is verified separately.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import stat

import pytest

WORKTREE = Path(__file__).resolve().parents[1]
RELEASE_PATH = WORKTREE / "deploy/mautic/release_readonly_inbox_existing_crm_20261121.py"
OVERLAY_PATH = WORKTREE / "deploy/mautic/mautic_readonly_existing_crm_overlay_20261121.py"


def load_release():
    spec = importlib.util.spec_from_file_location("mautic_readonly_release_fixture", RELEASE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_private_source_digest_and_only_review_modules():
    release = load_release()
    assert release.ROOT.name == "crm-mautic-readonly-20261121-v3"
    assert release.PRIOR.name == "crm-documents-firstparty-20261121-v2"
    assert release.UNIT == "empire-revenue-crm-pilot.service"
    assert release.REVIEW == "/v1/revenue-crm/integrations/mautic/inbox/reviews"
    assert len(release.SOURCES) == 3
    assert set(release.SOURCES) == {
        "deploy/mautic/mautic_readonly_existing_crm_overlay_20261121.py",
        "empire_os/mautic_crm_review_api.py",
        "empire_os/mautic_crm_inbox.py",
    }
    for relative, (_dest, digest) in release.SOURCES.items():
        from hashlib import sha256
        assert sha256((WORKTREE / relative).read_bytes()).hexdigest() == digest
        assert len(digest) == 64


def test_overlay_keeps_current_auth_and_one_get_only():
    code = OVERLAY_PATH.read_text()
    assert "from crm_search_additive_20261109.entrypoint import resolver" in code
    assert 'resolve_authenticated_read=resolver' in code
    assert 'if actual != {("GET", REVIEW)}:' in code
    assert "app.include_router(router)" in code
    assert "mautic_crm_integration" not in code
    assert "create_mautic_crm_preview_router" not in code
    assert "outbound_send" not in code
    assert "smtp" not in code.lower()
    assert "mautic_crm_inbox" in code
    assert "crm-mautic-readonly-20261121-v3" in code


def test_release_remains_reversible_and_preserves_three_auth_surfaces():
    source = RELEASE_PATH.read_text()
    assert "--activate-founder-approved-readonly-inbox-20261121" in source
    assert "original_crm_owner_entrypoint_changed" in source
    assert "mautic_review_live_http_readback_failed" in source
    assert "original_crm_route_regression" in source
    assert 'DROP.unlink(missing_ok=True)' in source
    assert 'run("systemctl", "daemon-reload"' in source
    assert 'run("systemctl", "restart", UNIT' in source
    assert '"/v1/revenue-crm/prospects": 401' in source
    assert '"/v1/revenue-crm/predictive-diagnostic": 401' in source
    assert '"/v1/revenue-crm/documents": 307' in source
    assert "no_webhook_ingress" in source
    assert "no_outbound_authority" in source
    assert "CREATE ROLE" not in source
    assert "INSERT INTO" not in source
    assert "docker compose up" not in source


def test_pinned_source_rejects_writable_and_symlink(tmp_path):
    from hashlib import sha256
    release = load_release()
    path = tmp_path / "immutable.py"
    path.write_bytes(b"example")
    path.chmod(0o644)
    digest = sha256(path.read_bytes()).hexdigest()
    release.pinned(path, digest)
    path.chmod(0o664)
    with pytest.raises(RuntimeError, match="pinned_file_invalid"):
        release.pinned(path, digest)
    path.unlink()
    target = tmp_path / "target"
    target.write_bytes(b"example")
    path.symlink_to(target)
    with pytest.raises(RuntimeError, match="pinned_file_invalid"):
        release.pinned(path, digest)
