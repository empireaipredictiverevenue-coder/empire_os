# Empire AI YouTube ChatGPT plugin — private MCP verification

Date: 2026-10-17. Owner: existing EmpireOS Media OS. Not released.

## What was verified
- Portable `plugin.json` validates against the official Agent Plugins v1.0.0 schema retrieved from `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`.
- Source package is `plugins/empire-youtube-intelligence/`; real tool facade is `empire_os/youtube_public_plugin_mcp.py`; the existing YouTube oEmbed reader supplies actual public title/author without vidIQ or any private channel API.
- Real Streamable HTTP SDK session: local server on ephemeral `127.0.0.1` port; session initialise, list tools, and call `empire_youtube_public_video_review`. Verified Paul Ponna video ID `j6JlWhDw-2w`, no transcript/watch/view-count claim. Forged YouTube hostname rejected.
- Loopback process terminated after test. No persistent systemd service, tunnel or DNS route.
- Five targeted unit tests plus protocol smoke, with the rest of the YouTube/Media contracts previously passing.

## Critical packaging order
Public docs: `https://developers.openai.com/plugins/deploy/submission`. **Adding an MCP server to an existing skills-only plugin is not currently supported.** Therefore do NOT call Plugin Creator to publish a skills-only package with the eventual official public name; add a legitimate remote MCP entry to `mcp.json` and validate that before creating the intended ChatGPT plugin. Do not fake the URL or point it at 127.0.0.1.

## Do not do these things
- Never attach `empire_os.ops_mcp`, `empire-ops-mcp`, root helper, shell/repository tools or the currently open founder console to customer traffic.
- Never expose `127.0.0.1:8877` to a public host with a tunnel, modify Cloudflare routing or add systemd starts based only on passing a private test.
- No face/voice/video uploads, data capture, payments, new infrastructure, auto-video publication, unverified statistics or paid inference.
- Do not present Plugin Creator availability as proof that the plugin is connected/published; privately creating/uploading a plugin is distinct from directory publication.

## Remaining exact requirements before public MCP
1. Add a narrow route under the **existing** gateway with separate public-service auth policy, per-client quota/caching, abuse limits and strict request sizes. Reject every non-public tool and tenant/client scope. Design and test privately first. Founder approval is required for exposure, route changes or activation.
2. For anonymous public-only tools, weigh approved `auth.type=none` with hard caching and rate controls. For user-specific features, OAuth with independently verified access to their own account is required. Server never trusts a model-selected tenant ID.
3. Validate public HTTPS endpoint and directory-reachable MCP: `initialize`, `tools/list`, `tools/call`, invalid URL, long input, timeout, rate-limit and no secrets. Provide the exact legitimate HTTPS URL and `mcp.json` in the **first** plugin ZIP.
4. Verify publisher identity, metadata/logo/privacy/support, product utility and eligible commerce behavior. Plugin tools must be helpful without paywall upsell messages. Read `https://developers.openai.com/plugins/resources/plugin-guidelines`.
5. Use the verified publication flow and review; no public listing or installations are assumed until confirmed by the platform.

## Repeat private probe
```bash
cd /srv/empire_os
./.venv/bin/python scripts/probe_youtube_public_plugin_mcp_loopback.py
./.venv/bin/python -m pytest -q tests/test_youtube_public_plugin_mcp.py tests/test_youtube_intelligence.py tests/test_youtube_read_adapter.py tests/test_media_production_contracts.py
```

**State:** PRIVATE_MCP_PROTOCOL_VERIFIED / PUBLIC_RELEASE_HELD / CUSTOMER_AUTH_NOT_CONFIGURED / LIVE_BENCHMARK_KEY_NOT_CONFIGURED.
