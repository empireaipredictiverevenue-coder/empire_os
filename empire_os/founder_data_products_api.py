"""Read-only Founder catalogue for Intelligence Data Products."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from empire_os.intelligence_data_products import (
    data_product_catalog,
    get_data_product,
)


def create_founder_data_products_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-data-products",
        tags=["founder-data-products"],
    )

    @router.get("")
    def list_products():
        return {
            "schema_version": "empire.founder_data_products.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "products": data_product_catalog(),
        }

    @router.get("/{product_key}")
    def get_product(product_key: str):
        product = get_data_product(product_key)
        if product is None:
            raise HTTPException(404, "data product not found")
        return product.as_dict()

    return router
