# Empire Ops Connector Doctrine

Status: CANONICAL
Applies to: EmpireOS operations, development agents, founder tooling and external AI clients.

## Decision

Empire Ops MCP is the canonical server-native operations/control connector for EmpireOS.

It is infrastructure owned by Empire. External AI products, chat clients and remote-control tools connect **to** Empire Ops; EmpireOS must not depend on those clients in order to operate.

## Client hierarchy

Primary control plane:

- Empire Ops MCP
- Empire privileged helper for narrowly allowlisted system actions
- Empire audit trail
- Empire protected-path and execution policy

Supported clients:

- Founder Console
- Empire Coder
- Hermes
- internal agents
- ChatGPT/custom MCP clients when transport/account support permits
- future operator apps

Fallback only:

- Desktop Commander / other third-party remote-control connectors

Desktop Commander may be used for bootstrap, recovery or emergency access, but it is not a canonical runtime dependency.

## Operating rule

A quota, outage, plan restriction or policy change in an external client must never be able to stop:

- acquisition
- qualification
- Astra
- buyer/closer processing
- Revenue Pulse
- scheduled workers
- product/catalog refreshes
- canonical data writes
- permitted internal automation

Those systems run server-side whether or not any external chat client is connected.

## Security boundary

Empire Ops must remain narrower than a general remote shell.

Required properties:

- bearer-token or stronger authenticated remote transport
- audited tool calls
- explicit tool allowlists
- no unrestricted shell
- protected `recovery/` and `toop/` paths
- no `git add .`
- explicit path staging/commits
- privileged actions mediated through the root-owned helper
- commercial truth only from canonical evidence
- no autonomous expansion of authority
- no funds movement, binding-term acceptance or revenue recognition without the corresponding governed gate

## Transport strategy

The MCP server may remain loopback-bound on the host and be exposed through a secure Empire-controlled transport/tunnel when remote clients need access.

Remote exposure must preserve:

- TLS
- bearer/OAuth-compatible authentication
- resource validation
- request auditability
- rate limiting where appropriate
- minimal public surface
- no direct exposure of the privileged helper socket

## Failure strategy

If a remote client cannot connect:

1. EmpireOS continues operating server-side.
2. Founder Console remains the primary truth surface.
3. Internal agents continue through Empire-owned interfaces.
4. Another compatible MCP client may connect.
5. Desktop Commander may be used only as a bootstrap/fallback route.

## Goal

Empire Ops is the stable contract. AI clients are replaceable.

This prevents EmpireOS from being operationally dependent on any single vendor, subscription tier, UI, quota or connector ecosystem.
