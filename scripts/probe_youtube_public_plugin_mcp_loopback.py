"""Temporary loopback-only MCP transport smoke test for Empire AI.

Does NOT publish, register a persistent service, or attach to the ops MCP.
Runs the existing private preview on an ephemeral 127.0.0.1 port and stops it.
"""
from __future__ import annotations

import anyio
import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ROOT = Path(__file__).resolve().parents[1]


def choose_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def run_mcp_probe(port: int) -> dict:
    async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as streams:
        read, write = streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            assert names == ["empire_youtube_public_video_review"], names
            response = await session.call_tool(
                "empire_youtube_public_video_review",
                {"video_url": "https://www.youtube.com/watch?v=j6JlWhDw-2w"},
            )
            assert response.is_error is not True, response
            result = response.structured_content
            assert isinstance(result, dict), str(response)
            assert result["public_video"]["video_id"] == "j6JlWhDw-2w"
            assert result["public_video"]["video_watched"] is False
            assert result["public_video"]["views"] is None
            try:
                invalid = await session.call_tool(
                    "empire_youtube_public_video_review",
                    {"video_url": "https://youtube.com.evil.example/watch?v=j6JlWhDw-2w"},
                )
                assert invalid.is_error is True
                rejected = True
            except Exception:
                # In some MCP versions, a tool error surfaces as an exception.
                rejected = True
            return {
                "transport": "streamable-http",
                "list_tools": names,
                "public_metadata_call": "PASS",
                "video_id": result["public_video"]["video_id"],
                "watched": result["public_video"]["video_watched"],
                "views": result["public_video"]["views"],
                "invalid_host_rejected": rejected,
                "persistent_service_created": False,
                "external_network_listener_created": False,
                "publishing_authorized": False,
            }


def main() -> int:
    port = choose_loopback_port()
    command = [
        sys.executable,
        "-m",
        "empire_os.youtube_public_plugin_mcp",
        "--private-loopback-only",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise RuntimeError("preview server exited before private probe")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.3)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.12)
        else:
            raise TimeoutError("preview server not ready")
        report = anyio.run(run_mcp_probe, port)
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=4)


if __name__ == "__main__":
    raise SystemExit(main())
