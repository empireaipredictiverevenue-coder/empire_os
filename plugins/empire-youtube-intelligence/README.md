# Empire AI YouTube Intelligence — portable private preview

This package has a real portable `plugin.json` plus two bundled skills, but **no remote `mcp.json`** yet. An MCP URL would be invalid to publish today: we have no founder-approved public customer endpoint or entitlement/auth rate limits. Never substitute the internal Empire Ops MCP URL for a public URL.

The matching **private-only**, code-reviewed MCP facade lives in the same EmpireOS repository at `empire_os/youtube_public_plugin_mcp.py`. It provides one useful read-only tool: `empire_youtube_public_video_review(video_url)`, using `youtube_read_adapter.read_public_youtube_oembed`. The preview may be started only locally on 127.0.0.1 with explicit `--private-loopback-only`; it has no customer auth, throttling, or publishing approval and **must not be exposed externally**.

Next steps: test private MCP and skill, design public service rate limits and auth, decide if the first release is skills-only or an MCP+skills plugin; complete business verification and the plugin listing, validate with test users, and submit only after the public connection passes an independent security review.

Policies: https://developers.openai.com/plugins/build/plugins ; https://developers.openai.com/plugins/deploy/submission ; https://developers.openai.com/plugins/resources/plugin-guidelines .
