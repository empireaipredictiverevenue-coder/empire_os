# Empire Remote Commander

Status: CODE COMPLETE / LIVE BOOTSTRAP REQUIRED

## Purpose

Empire Remote Commander is the canonical Empire-owned remote operations plane.
It replaces third-party Remote Desktop Commander as the primary engineering
connection while retaining Desktop Commander as emergency bootstrap/fallback.

## Architecture

```text
ChatGPT / Codex / Founder Console
        |
        | MCP over TLS
        v
mcp.empire-ai.co.uk
        |
        v
Cloudflare Tunnel
        |
        v
127.0.0.1:8765/mcp
        |
        v
Empire Remote Commander / Ops MCP
        |
        +--> typed repo/file/test/log/service operations
        |
        +--> root-owned privileged helper for allowlisted service actions only
        |
        +--> audit.jsonl
```

Fallback:

```text
ChatGPT -> GitHub ops/hermes-control -> deterministic ops_request
        -> Empire Remote Commander core -> encrypted result -> GitHub
```

Both transports call the same `empire_os.remote_commander.execute()` policy
surface.

## Supported engineering operations

- health
- repository status/log/diff
- directory listing
- repository content search
- bounded file reads
- SHA-guarded repository file writes
- Python compile
- targeted pytest
- git diff check
- allowlisted service status
- allowlisted journal tail
- aggregate runtime health
- environment-key presence only
- Founder Directive intake

The MCP surface additionally supports privileged service start/restart through
the existing root-owned helper, with preview mode by default.

## Explicitly unavailable

Remote Commander does not expose:

- arbitrary shell strings
- unrestricted argv execution
- arbitrary sudo
- arbitrary systemd units
- package installation
- direct DNS changes
- direct database mutation
- outbound email/SMS/voice sending
- payments/funds movement
- binding commercial terms
- authority expansion
- protected recovery/toop mutation

## Credentials

The permanent credential is NOT the founder's personal SSH key.

`scripts/rotate_empire_remote_commander_token.py` creates a random bearer
secret and stores it at:

`/etc/empire_os/remote-commander.env`

Permissions are 0600. The secret is never printed. Only its SHA-256 fingerprint
is shown for verification.

The personal SSH credential is used only to bootstrap/recover the server if
another remote control path is unavailable.

## Activation

Repository build and live activation are deliberately separate.

`scripts/install_empire_remote_commander.sh` verifies code/tests, installs the
service/drop-in, and creates credentials if absent. Without `--activate`, it
stops before starting/enabling services.

Live activation additionally requires:

1. the MCP service running on loopback;
2. a Cloudflare Tunnel hostname such as `mcp.empire-ai.co.uk`;
3. authenticated MCP verification from an external client;
4. no public exposure of port 8765;
5. audit-log verification;
6. fallback Hermes bridge verification.

## Product rule

Empire Remote Commander is the stable contract. ChatGPT, Codex, Hermes,
Founder Console and any future client are replaceable clients of that contract.
