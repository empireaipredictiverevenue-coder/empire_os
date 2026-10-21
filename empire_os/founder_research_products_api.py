"""Private Founder read-only preview of Empire Research and Empire Agent.

Only mount inside the already private/loopback Founder Console service after
its original owner approves a guarded release and trusted session boundary.
Not a public, tenant-self-service endpoint or model-execution permission.
"""
from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, Query

from empire_os.research.research_products import product_catalog, use_product


def create_founder_research_products_router(
    product_runner: Callable = use_product,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-research-products",
        tags=["founder-research-products-private"],
    )

    @router.get("/catalog")
    def catalog():
        return product_catalog()

    @router.get("/preview")
    def preview(
        product: Literal["empire_research", "empire_agent"] = Query(...),
        country: Literal["US", "GB", "both"] = Query("both"),
        niche: Literal["dental", "roofing", "solar", "hvac", "legal",
                       "property"] = Query("dental"),
        depth: Literal["speed", "balanced", "quality"] = Query("quality"),
    ):
        return product_runner(product, country=country, niche=niche, depth=depth)

    return router
