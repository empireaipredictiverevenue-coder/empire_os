"""Staged fail-closed middleware for the EXISTING NVIDIA Auto Ontology FastMCP.

Install only after canonical EmpireOS subject linkage, existing CRM membership
reader, and dedicated/RLS data-plane attestor are wired and live verified.
The current synthetic shared deployment is deliberately NOT activated with
this middleware. Its absence is a release hold, not proof of isolation.
"""
from __future__ import annotations

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from empire_os.nvidia_ontology_tenant_policy import (
    NvidiaTenantAccessPolicy, NvidiaTenantDenied,
)

# All nine native vendor tool calls go through on_call_tool. Neither caller
# arguments (including target_db) nor X-headers are used as tenant authority.
def authenticated_subject_from_fastmcp() -> str | None:
    from fastmcp.server.dependencies import get_access_token

    try:
        token = get_access_token()
    except Exception:
        return None
    value = getattr(token, "subject", None)
    return value if isinstance(value, str) and value else None


class NvidiaTenantCallBoundary(Middleware):
    def __init__(self, policy: NvidiaTenantAccessPolicy):
        self._policy = policy

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        try:
            subject = authenticated_subject_from_fastmcp()
            verdict = self._policy.authorize(subject)
            if not verdict.allowed:
                raise NvidiaTenantDenied("CANONICAL_TENANT_ACCESS_DENIED")
        except NvidiaTenantDenied as exc:
            # Uniform external failure: callers cannot distinguish the
            # presence of another tenant's datasource or membership.
            raise ToolError("NVIDIA_TENANT_SCOPE_REQUIRED") from exc
        return await call_next(context)


def install_nvidia_tenant_boundary(mcp, policy: NvidiaTenantAccessPolicy) -> None:
    """Single optional middleware on the original MCP; no tool replacement."""
    if not isinstance(policy, NvidiaTenantAccessPolicy):
        raise TypeError("original EmpireOS tenant policy required")
    mcp.add_middleware(NvidiaTenantCallBoundary(policy))
