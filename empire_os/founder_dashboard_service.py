"""Minimal read-only Founder Console API service.

This deliberately excludes the full EmpireOS hub lifespan and all write-capable
routers. It is intended for loopback-only consumption by the Founder Console.
"""
from __future__ import annotations

from fastapi import FastAPI

from empire_os.founder_dashboard_api import create_founder_dashboard_router
from empire_os.founder_daily_results_api import create_founder_daily_results_router
from empire_os.founder_directives_api import create_founder_directives_router
from empire_os.founder_data_products_api import create_founder_data_products_router
from empire_os.founder_intelligence_nodes_api import create_founder_intelligence_nodes_router
from empire_os.founder_objectives_api import create_founder_objectives_router
from empire_os.founder_ops_api import create_founder_ops_router
from empire_os.revenue_pulse_api import create_revenue_pulse_router
from empire_os.spatial_physical_api import create_spatial_physical_router

app = FastAPI(
    title="Empire Founder Read API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(create_founder_dashboard_router())
app.include_router(create_founder_daily_results_router())
app.include_router(create_founder_directives_router())
app.include_router(create_founder_intelligence_nodes_router())
app.include_router(create_founder_data_products_router())
app.include_router(create_revenue_pulse_router())
app.include_router(create_spatial_physical_router())
app.include_router(create_founder_objectives_router())
app.include_router(create_founder_ops_router())


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "founder-dashboard-read-api",
        "read_only": True,
    }
