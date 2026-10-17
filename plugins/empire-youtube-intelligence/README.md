# Empire AI YouTube Intelligence — private plugin v0.2.0

**Canonical installed ChatGPT private plugin**: `plugins_6ad3b84a3dec819193d8836ed6866a4b`, version `0.2.0`, original installed release `pluginrel_6ad3c32f1b948191ac1ba94a6921dace`. This repository folder now mirrors that release's manifests, two skills and two founder-approved Empire AI globe/logo PNGs. The installed plugin was not changed by this source sync. Both logo and icon are 1024x1024 square PNGs.

This is a **skills-only private plugin**: no customer-facing remote `mcp.json` is attached. Do not claim live YouTube competitor analysis, private channel analytics, automatic video rendering or a public directory listing from this version.

The matching private-only code-reviewed MCP facade is in `empire_os/youtube_public_plugin_mcp.py`, built on the existing `empire_os/youtube_read_adapter.py`. It is restricted to localhost and was never activated for external customers. It **must not** be confused with or connected to the privileged `empire-ops-mcp.service`.

The other chat independently develops next-version MCP research tools inside `feature/empire-youtube-intelligence-p0-20261017` (or its successor feature worktree). Do not duplicate that work. Any new release must preserve the original plugin backend ID and this branding; reconcile its feature branch into the existing repo first, run the full tests, then explicitly update this same private plugin.

Publication readiness still requires operational remote customer MCP, tenant/security review, API quota and auth tests, independent benchmarking on live data, validated privacy/support, founder approval and platform review. ChatGPT public publication is **not** authorized by this repository commit.

References: https://developers.openai.com/plugins/build/plugins and https://developers.openai.com/plugins/deploy/submission.
