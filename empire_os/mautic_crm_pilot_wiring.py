"""Explicit founder-gated Mautic source wiring into existing Smart CRM pilot.

No application registration on import. This is *not* an identity resolver:
the founder/CRM owner must independently establish exact canonical contact
bindings before an approved, private, immutable source file is provisioned.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID

from fastapi import APIRouter, Request

from empire_os.mautic_crm_inbox import PostgresMauticEventInbox
from empire_os.mautic_crm_integration import (
    MauticSource, create_mautic_crm_preview_router,
)
from empire_os.mautic_crm_review_api import create_mautic_crm_review_router
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

SOURCE_SCHEMA = "empire.mautic_crm_source_pilot.v1"
_SOURCE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$", re.ASCII)
_APPROVAL = re.compile(r"^[A-Za-z0-9:@._/-]{12,160}$", re.ASCII)
_CONTACT = re.compile(r"^[1-9][0-9]{0,17}$", re.ASCII)
_WRITER = re.compile(r"^empire_mautic_tenant_[0-9a-f]{12,32}$", re.ASCII)
_SECRET = re.compile(rb"^[0-9a-f]{64}$")


def _no_duplicate_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicated Mautic source configuration key")
        data[key] = value
    return data


def build_mautic_pilot_routers(
    *,
    config_path: Path,
    crm_founder_approval_ref: str,
    tenant_dsns: Mapping[str, str],
    resolve_authenticated_read: Callable[
        [Request], AuthenticatedRevenueCrmRead | None
    ],
    read_private_bytes: Callable[..., bytes],
    parse_dsn_role: Callable[[object], str],
) -> tuple[APIRouter, APIRouter]:
    """Construct 2 inactive-until-mounted routers for a SINGLE reviewed source.

    The existing CRM pilot supplies authenticated tenant reader credentials.
    A separate, founder-approved Mautic source configuration supplies only
    signed ingress and its distinct, tenant-bound inbox writer. Neither
    function creates an OS/DB user, executes DDL, discovers contacts, sends,
    or updates CRM records.
    """
    if not isinstance(config_path, Path):
        raise ValueError("private Mautic config path required")
    raw = read_private_bytes(config_path, limit=64 * 1024)
    try:
        config = json.loads(raw, object_pairs_hook=_no_duplicate_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid private Mautic JSON") from None
    if (
        not isinstance(config, dict)
        or set(config) != {
            "schema_version", "founder_approval_ref", "source_id",
            "tenant_id", "source_evidence_ref", "webhook_secret_file",
            "writer_dsn", "contact_bindings",
        }
        or config["schema_version"] != SOURCE_SCHEMA
    ):
        raise ValueError("exact separately approved Mautic source configuration required")
    approval = config["founder_approval_ref"]
    provenance = config["source_evidence_ref"]
    if (
        not isinstance(approval, str)
        or not _APPROVAL.fullmatch(approval)
        or approval == crm_founder_approval_ref
        or not isinstance(provenance, str)
        or not _APPROVAL.fullmatch(provenance)
    ):
        raise ValueError("distinct Mautic founder approval and source provenance required")
    source_id = config["source_id"]
    if not isinstance(source_id, str) or not _SOURCE.fullmatch(source_id):
        raise ValueError("invalid server-owned Mautic source identifier")
    try:
        tenant = str(UUID(config["tenant_id"]))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid approved Mautic tenant") from None
    if tenant != config["tenant_id"] or tenant not in tenant_dsns:
        raise ValueError("Mautic source not bound to approved CRM tenant")

    writer_dsn = config["writer_dsn"]
    writer_role = parse_dsn_role(writer_dsn)
    if (
        not _WRITER.fullmatch(writer_role)
        or writer_dsn in tenant_dsns.values()
    ):
        raise ValueError("distinct dedicated Mautic tenant writer login required")
    # No permission changes occur: actual role, RLS, and login authority
    # must independently pass the PostgresMauticEventInbox runtime check.
    secret_path = config["webhook_secret_file"]
    if not isinstance(secret_path, str):
        raise ValueError("private Mautic signing secret file required")
    secret = read_private_bytes(Path(secret_path), limit=512)
    if not _SECRET.fullmatch(secret):
        raise ValueError("64-character hex Mautic source secret required")

    declared = config["contact_bindings"]
    if not isinstance(declared, dict) or not 1 <= len(declared) <= 200:
        raise ValueError("bounded verified Mautic contact bindings required")
    bindings: dict[int, dict[str, str]] = {}
    seen_prospects: set[str] = set()
    for raw_id, binding in declared.items():
        if not isinstance(raw_id, str) or not _CONTACT.fullmatch(raw_id):
            raise ValueError("canonical Mautic numeric contact ID required")
        if not isinstance(binding, dict) or set(binding) != {
            "prospect_id", "identity_evidence_ref",
        }:
            raise ValueError("exact reviewed source-to-prospect identity required")
        raw_prospect = binding["prospect_id"]
        identity_proof = binding["identity_evidence_ref"]
        try:
            prospect_id = str(UUID(raw_prospect))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("canonical CRM prospect UUID required") from None
        if (
            prospect_id != raw_prospect or prospect_id in seen_prospects
            or not isinstance(identity_proof, str)
            or not _APPROVAL.fullmatch(identity_proof)
        ):
            raise ValueError("duplicate/unproven Mautic contact binding")
        seen_prospects.add(prospect_id)
        bindings[int(raw_id)] = {
            "tenant_id": tenant, "prospect_id": prospect_id,
        }

    source = MauticSource(
        source_id=source_id, tenant_id=tenant,
        webhook_secret=secret, contact_bindings=bindings,
    )
    inbox = PostgresMauticEventInbox(
        writer_dsn, authenticated_tenant_id=tenant,
    )
    def resolve_source(candidate: str) -> MauticSource | None:
        return source if candidate == source_id else None

    def resolve_tenant_reader(candidate: str):
        dsn = tenant_dsns.get(candidate) if candidate == tenant else None
        return (
            PostgresRevenueCrmRepository(dsn, tenant_id=tenant)
            if dsn is not None else None
        )

    return (
        create_mautic_crm_preview_router(
            resolve_source=resolve_source,
            resolve_tenant_reader=resolve_tenant_reader,
            receipt_journal=inbox,
        ),
        create_mautic_crm_review_router(
            resolve_authenticated_read=resolve_authenticated_read,
        ),
    )
