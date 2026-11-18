"""Compatibility fix for existing NVIDIA MCP check_readiness in EmpireOS.

NVIDIA /api/connections lists only UI-managed entries. The existing
CONNECTION_STRINGS integration is reported separately at
/api/connections/source. A false "no connection configured" warning under
a valid environment-managed connection made the existing Viewer tool
misleading. Preserve the one original tool name, role checks and interface;
never create a connection or query raw SQL from this readiness probe.

This is a configuration/readiness signal, NOT executed SQL evidence.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from fastmcp import FastMCP
from auto_ontology_mcp import readiness

LOG=logging.getLogger(__name__)
ENV_SOURCE_PATH="/api/connections/source"
ENV_NOTE=(
    "Connection is environment-managed (CONNECTION_STRINGS), not listed in "
    "UI-managed connections. Readiness confirms configuration only; successful "
    "SQL execution must be independently verified."
)
MISSING_MESSAGE_PREFIX="No database connection is configured"


async def install(mcp:FastMCP, client:httpx.AsyncClient)->None:
    """Replace one vendor tool in place; preserve its schema and description."""
    prior=await mcp.get_tool("check_readiness")
    if prior is None:
        raise RuntimeError("Expected pinned NVIDIA check_readiness missing")
    original_description=prior.description
    mcp.local_provider.remove_tool("check_readiness")

    @mcp.tool(name="check_readiness", description=original_description)
    async def check_readiness()->readiness.Readiness:
        status, connections, databases, env_source = await asyncio.gather(
            readiness._probe(client,readiness.STATUS_PATH),
            readiness._probe(client,readiness.CONNECTIONS_PATH),
            readiness._probe(client,readiness.DATABASES_PATH),
            readiness._probe(client,ENV_SOURCE_PATH),
        )
        result=readiness._summarise(status,connections,databases)
        no_ui_connections=(
            isinstance(connections,dict)
            and not int(connections.get("count") or 0)
        )
        if no_ui_connections and env_source is True:
            # An authenticated caller can check this public, permission-gated
            # endpoint. An environment-managed connector is configured even
            # though the UI storage has no connection rows. As with UI
            # connections, the count does not prove execution.
            result.can_execute_sql=True
            result.blockers=[
                b for b in result.blockers
                if not b.startswith(MISSING_MESSAGE_PREFIX)
            ]
            result.ready=not bool(result.blockers)
            result.unverified.append(ENV_NOTE)
        if not result.ready:
            LOG.info("NVIDIA readiness blockers: %s", "; ".join(result.blockers))
        return result

    if await mcp.get_tool("check_readiness") is None:
        raise RuntimeError("NVIDIA readiness replacement failed")
