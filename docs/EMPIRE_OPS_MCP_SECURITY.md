# Empire Ops MCP Security Boundary

## Goal

Replace general-purpose remote shell dependence with an Empire-owned,
allowlisted operations surface.

## Current architecture

```
local/authorized MCP client
        |
        v
Empire Ops MCP (ubuntu, loopback :8765)
        |
        | audited typed request
        v
Unix socket /run/empire-ops/privileged.sock
        |
        v
Root privileged helper
        |
        v
fixed systemctl action + fixed Empire unit allowlist
```

The helper does **not** accept shell text, arbitrary argv, arbitrary units,
unit installation, daemon reload, package management, file mutation, secrets,
database commands, payment commands, or outbound-send commands.

## Privileged actions

Supported helper actions are intentionally narrow:

- service status;
- restart an allowlisted Empire runtime service;
- start an allowlisted oneshot/internal worker.

The MCP-facing service-control tool is preview-only unless
`execute=true` is supplied. All MCP calls continue through the existing
Ops audit log.

## Unix-socket authorization

The privileged helper:

- runs as root;
- creates `/run/empire-ops/privileged.sock`;
- uses a root-owned runtime directory;
- uses group permissions for the unprivileged Ops MCP process;
- verifies Linux peer credentials with `SO_PEERCRED`;
- accepts only root or the configured `ubuntu` service user.

This is independent of HTTP authentication.

## HTTP authentication

Streamable HTTP remains bound to `127.0.0.1` by default.

If `EMPIRE_OPS_MCP_BEARER_TOKEN` is configured, Ops MCP enables the MCP
SDK bearer-token resource-server gate with scope `empire:ops`.
`EMPIRE_OPS_MCP_RESOURCE_URL` and `EMPIRE_OPS_MCP_ISSUER_URL` define
the protected resource metadata.

The long-term identity edge is Authentik/OIDC. Do not expose port 8765
directly to the public Internet. A future remote route should sit behind the
approved identity/proxy layer and use a real issuer/JWT verifier.

## Authority boundaries

Ops MCP still cannot:

- send outbound email;
- accept commercial terms;
- move funds;
- verify payment by mutation;
- recognize revenue;
- alter model weights;
- widen its own allowlist;
- edit protected `recovery/` or `toop`;
- run a general shell.

Adding a new privileged unit or action requires a reviewed repository change.
