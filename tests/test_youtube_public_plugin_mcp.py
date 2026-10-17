"""Private preview of consumer-facing Empire AI YouTube plugin."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from empire_os import youtube_public_plugin_mcp


PKG = Path(__file__).resolve().parents[1] / "plugins" / "empire-youtube-intelligence"


def test_package_has_portable_manifest_and_does_not_publish_ops_mcp():
    manifest = json.loads((PKG / "plugin.json").read_text())
    assert manifest["name"] == "empire-youtube-intelligence"
    assert manifest["$schema"].endswith("plugin.schema.json")
    assert manifest["version"] == "0.2.0"
    interface = manifest["extensions"]["com.openai"]["interface"]
    assert interface["displayName"] == "Empire AI YouTube Intelligence"
    assert interface.get("capabilities") in (None, [])  # Skills-only package.
    assert interface["composerIcon"] == "./assets/icon.png"
    assert interface["logo"] == "./assets/logo.png"
    for asset in ("assets/icon.png", "assets/logo.png"):
        data = (PKG / asset).read_bytes()
        assert data[:8] == bytes((137, 80, 78, 71, 13, 10, 26, 10))
        from struct import unpack
        width, height = unpack(">II", data[16:24])
        assert width == height and width >= 512
    codex_manifest = json.loads((PKG / ".codex-plugin" / "plugin.json").read_text())
    assert codex_manifest["name"] == manifest["name"]
    assert codex_manifest["version"] == manifest["version"]
    assert not (PKG / "mcp.json").exists()  # No invented public endpoint.
    assert (PKG / "skills" / "setup" / "SKILL.md").exists()
    assert (PKG / "skills" / "youtube-research" / "SKILL.md").exists()


def test_public_review_reuses_existing_reader_without_claiming_video_watched(monkeypatch):
    def existing_reader(video_url):
        assert video_url == "https://youtube.com/watch?v=j6JlWhDw-2w"
        return {
            "video_id": "j6JlWhDw-2w",
            "title": "A published public video",
            "video_watched": False,
            "views": None,
            "read_only": True,
        }
    monkeypatch.setattr(youtube_public_plugin_mcp, "read_public_youtube_oembed", existing_reader)
    review = youtube_public_plugin_mcp.public_video_review(
        "https://youtube.com/watch?v=j6JlWhDw-2w"
    )
    assert review["status"] == "PUBLIC_METADATA_REVIEW"
    assert review["public_video"]["views"] is None
    assert review["execution_authority"] == "read_only"
    assert any("not watched" in phrase for phrase in review["limitations"])


def test_public_mcp_does_not_start_without_explicit_private_loopback(monkeypatch):
    called = False
    def should_not_run(**kwargs):
        nonlocal called
        called = True
    monkeypatch.setattr(youtube_public_plugin_mcp.server, "run", should_not_run)
    with pytest.raises(SystemExit):
        youtube_public_plugin_mcp.main([])
    assert not called


def test_private_preview_mcp_never_binds_public_interface(monkeypatch):
    kwargs = []
    monkeypatch.setattr(
        youtube_public_plugin_mcp.server, "run",
        lambda **params: kwargs.append(params),
    )
    youtube_public_plugin_mcp.main(["--private-loopback-only", "--port", "8899"])
    assert kwargs[0]["host"] == "127.0.0.1"
    assert kwargs[0]["stateless_http"] is True
    assert kwargs[0]["streamable_http_path"] == "/mcp"


def test_private_mcp_server_excludes_internal_ops_tools():
    server = youtube_public_plugin_mcp.server
    assert server.name != "empire_ops_mcp"
    assert not hasattr(youtube_public_plugin_mcp, "privileged_request")
    assert not hasattr(youtube_public_plugin_mcp, "git_status")
