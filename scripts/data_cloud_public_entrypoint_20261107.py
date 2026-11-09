"""Add the ORIGINAL read-only Data Cloud route to the current public gateway.

One original FastAPI app, no replacement service, no data providers or billing.
The public process receives only its own restricted meter credential and the
separate Data Cloud public verification key (never the signing private key).
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import empire_os
import psycopg
from psycopg.conninfo import make_conninfo
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

EXPECTED_FLAG = "FOUNDER_APPROVED_READ_ONLY_USAGE_20261107"
RELEASE = Path("/opt/empire-ai/data-cloud-founder-pilot-20261107")
CONFIG = Path("/var/lib/empire-data-cloud-founder-pilot/runtime.json")
BASE = Path("/srv/empire_os/empire_os")

if os.environ.get("EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE") != EXPECTED_FLAG:
    raise RuntimeError("data_cloud_founder_usage_not_approved")
if Path(empire_os.__file__).resolve().parent != BASE:
    raise RuntimeError("public_original_empire_os_package_changed")
if RELEASE.is_symlink() or not RELEASE.is_dir() or RELEASE.stat().st_mode & 0o022:
    raise RuntimeError("data_cloud_frozen_release_required")
if CONFIG.is_symlink() or not CONFIG.is_file() or stat.S_IMODE(CONFIG.stat().st_mode) != 0o600:
    raise RuntimeError("data_cloud_private_config_unavailable")
cfg = json.loads(CONFIG.read_text())
if cfg.get("scope") != "FOUNDER_ONLY_USAGE_NO_PROVIDERS" or cfg.get("release_version") != 1:
    raise RuntimeError("unexpected_data_cloud_release_scope")

# Import current active LinkedIn/browser gateway first. Its owners and router
# preserve exactly the existing release stack.
from linkedin_browser_ui_entrypoint import app  # noqa: E402
extension = RELEASE / "empire_os"
if extension.is_symlink() or not extension.is_dir():
    raise RuntimeError("data_cloud_package_missing")
empire_os.__path__.insert(0, str(extension))

from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader  # noqa: E402
from empire_os.predictive_cloud_founder_session import DataCloudPublicVerifier  # noqa: E402
from empire_os.predictive_cloud_customer_api.gateway_candidate_entrypoint import (  # noqa: E402
    create_gateway_candidate_app,
)
from empire_os.predictive_cloud_route_assembly import (  # noqa: E402
    USAGE_PILOT_REQUIREMENTS, attach_existing_customer_routes,
)

owner = cfg["owner_actor_id"]
tenant = cfg["owner_tenant_id"]
membership_dsn = cfg["crm_membership_dsn"]
crm_passfile = cfg["crm_membership_passfile"]
meter_password = cfg["meter_password"]

if not Path(crm_passfile).is_file() or not Path(crm_passfile).is_absolute():
    raise RuntimeError("original_crm_membership_passfile_missing")
member_reader = EmpireDbCrmMembershipReader(
    make_conninfo(membership_dsn, passfile=crm_passfile)
)
entitled = lambda actor, tenant_id: actor == owner and tenant_id == tenant
verifier = DataCloudPublicVerifier(
    live_membership=member_reader,
    data_entitlement=entitled,
    pinned_public_keys={
        cfg["data_signing_key_id"]: Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(cfg["data_signing_public_key_hex"])
        )
    },
)


def meter_connection():
    return psycopg.connect(
        dbname="empiredb",
        user="empire_data_cloud_meter_login",
        host="127.0.0.1",
        port=5432,
        password=meter_password,
        connect_timeout=3,
    )


search_flag = os.environ.get("EMPIRE_DATA_CLOUD_FOUNDER_SEARCH_RELEASE", "")
search_enabled = bool(search_flag)
search_evidence = None
search_options = {}
if search_enabled:
    from empire_os.predictive_cloud_search_release import FLAG, load_search_release
    if search_flag != FLAG:
        raise RuntimeError("unexpected_first_party_search_release_flag")
    search_evidence, request_policy, output_policy = load_search_release(
        CONFIG.parent / "SEARCH_RELEASE_EVIDENCE.json",
        expected_sha256=os.environ.get("EMPIRE_DATA_CLOUD_SEARCH_RECEIPT_SHA256", ""),
        release=RELEASE, owner=owner, tenant=tenant,
    )
    search_options = dict(
        enable_first_party_search=True,
        source_request_preflight=request_policy,
        source_output_check=output_policy,
    )
candidate = create_gateway_candidate_app(
    connect_factory=meter_connection, **search_options,
)


def actual_release_evidence():
    # The original protected operator must commit real release preflight
    # receipts before the gateway may import the customer usage route.
    evidence_path = CONFIG.parent / "RELEASE_EVIDENCE.json"
    if evidence_path.is_symlink() or not evidence_path.is_file():
        raise RuntimeError("missing_owner_release_receipt")
    evidence = json.loads(evidence_path.read_text())
    if (evidence.get("source_sql_sha256") !=
            "d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393"):
        raise RuntimeError("unrecognised_migration_source")
    if evidence.get("mode") != "FOUNDER_ONLY_USAGE_NO_PROVIDERS":
        raise RuntimeError("not_a_founder_usage_release")
    return evidence["verified_requirements"]


attached = attach_existing_customer_routes(
    app, candidate, verifier, usage_only=not search_enabled,
    search_pilot=search_enabled,
    release_evidence=(lambda: search_evidence) if search_enabled else actual_release_evidence,
)
if attached != (("/v1/data/search", "/v1/data/usage") if search_enabled else ("/v1/data/usage",)):
    raise RuntimeError("unexpected_founder_pilot_route_mount")
