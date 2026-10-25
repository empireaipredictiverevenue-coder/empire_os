"""EmpireOS Predictive Cloud V4.9 — additive, loopback-only, READ-ONLY route.

Reports code presence and real governance holds; does NOT connect to EmpireDB,
Redis, external sources, accounts, trading, payment, outbound or real buyers.
The caller cannot set rights, tenant, readiness or execution privileges.
This is an instrumentation endpoint, NOT a revenue engine activation.
"""
from __future__ import annotations

from fastapi import APIRouter, Response

from empire_os.predictive_cloud_v4_redis_shadow import (
    FEATURE_REVISION_FENCE_LUA, STREAM, feature_key,
)
from empire_os.predictive_cloud_v4_outbox_hold_reader import review_held_outbox
from empire_os.predictive_cloud_v47_admission_shadow import review_signed_source_fixture
from empire_os.predictive_cloud_v48_crm_bound_shadow import review_crm_bound_admission_fixture

PATH = "/v1/predictive-cloud/v4/shadow-readiness"
SCHEMA = "empire.predictive_cloud.v49.shadow_readiness.v1"


def build_v49_shadow_readiness() -> dict[str, object]:
    """Pure contract. True means IMPORTABLE CODE, not live source eligibility."""
    if not (
        callable(feature_key)
        and callable(review_held_outbox)
        and callable(review_signed_source_fixture)
        and callable(review_crm_bound_admission_fixture)
        and isinstance(STREAM, str) and STREAM.startswith("v4:stream:")
        and "EXPIRE" in FEATURE_REVISION_FENCE_LUA
    ):
        raise RuntimeError("V49_SHADOW_MODULES_INVALID")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SHADOW_CODE_LOADED_NON_EXECUTING",
        "original_empire_os": True,
        "canonical_database": "EmpireDB_PostgreSQL",
        "original_smart_crm_reader_reused": True,
        "local_shadow_modules_importable": True,
        "v4_redis_advisory_projection_implemented": True,
        "v4_held_outbox_reader_implemented": True,
        "v47_dual_signature_fixture_reviewer_implemented": True,
        "v48_crm_bound_fixture_reviewer_implemented": True,
        "real_source_rights_verified": False,
        "production_tenant_source_admitted": False,
        "empiredb_migrations_064_065_applied_by_this_release": False,
        "redis_cloud_producer_activated": False,
        "live_consumer_activated": False,
        "commercial_prediction_authorized": False,
        "outbound_authorized": False,
        "paid_traffic_authorized": False,
        "trading_authorized": False,
        "treasury_authorized": False,
        "recognized_revenue_cents": None,
        "read_only": True,
    }


def create_v49_shadow_readiness_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get(PATH)
    def v49_shadow_readiness(response: Response) -> dict[str, object]:
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return build_v49_shadow_readiness()

    return router
