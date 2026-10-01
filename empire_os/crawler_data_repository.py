"""Canonical data repository for crawler prospect lookup and ingest."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.prospect_ingest import (
    ProspectIngestError,
    match_existing_prospect,
)
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
PROSPECT_COLUMNS = (
    "id,business_name,phone,metro,niche,website,address,status,contact_source"
)


class CrawlerProspectRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "CrawlerProspectRepository":
        env = load_runtime_env(ENV_PATH)
        backend = env.get("EMPIRE_DATA_BACKEND", "empiredb").strip()
        if backend != "empiredb":
            raise ProspectIngestError("crawler requires canonical EmpireDB backend")
        env["EMPIRE_DATA_BACKEND"] = "empiredb"
        if not env.get("EMPIREDB_DSN"):
            database_env = load_runtime_env("/etc/empiredb.env")
            if database_env.get("EMPIREDB_DSN"):
                env["EMPIREDB_DSN"] = database_env["EMPIREDB_DSN"]
        return cls(gateway_from_environment(env))

    @property
    def backend_name(self) -> str:
        return self._gateway.backend.value

    def lookup_existing(
        self,
        prepared: dict[str, Any],
        *,
        page_size: int = 1000,
        max_pages: int = 10,
    ) -> dict[str, Any]:
        prospect = prepared.get("prospect")
        if not isinstance(prospect, dict):
            raise ProspectIngestError(
                "prepared candidate missing prospect payload"
            )
        metro = str(prospect.get("metro") or "").strip()
        if not metro:
            raise ProspectIngestError(
                "prepared candidate missing metro"
            )

        rows: list[dict[str, Any]] = []
        pages = 0
        truncated = False
        batch: list[dict[str, Any]] = []

        for page in range(max_pages):
            offset = page * page_size
            batch = self._gateway.query(
                "prospects",
                PROSPECT_COLUMNS,
                filters=(DataFilter.ilike("metro", metro),),
                order=(OrderSpec("created_at"),),
                limit=page_size,
                offset=offset,
            )
            pages += 1
            rows.extend(batch)
            if len(batch) < page_size:
                break
        else:
            if batch and len(batch) >= page_size:
                truncated = True

        if truncated:
            return {
                "decision": "ambiguous",
                "reason": "prospect_lookup_truncated",
                "prospect": None,
                "rows_scanned": len(rows),
                "pages_scanned": pages,
            }

        result = match_existing_prospect(prepared, rows)
        return {
            **result,
            "rows_scanned": len(rows),
            "pages_scanned": pages,
        }

    def ingest_atomic(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        prospect = payload.get("prospect")
        evidence = payload.get("evidence")
        ingest_key = payload.get("ingest_key")
        identity_keys = payload.get("identity_keys")
        if not isinstance(prospect, dict):
            raise ProspectIngestError("canonical prospect writer missing prospect")
        if not isinstance(evidence, dict):
            raise ProspectIngestError("canonical prospect writer missing evidence")
        if not isinstance(ingest_key, str) or not ingest_key:
            raise ProspectIngestError("canonical prospect writer missing ingest_key")
        if (
            not isinstance(identity_keys, list)
            or not identity_keys
            or not all(isinstance(key, str) and key for key in identity_keys)
        ):
            raise ProspectIngestError("canonical prospect writer missing identity_keys")

        result = self._gateway.rpc(
            "ingest_prospect_atomic",
            {
                "p_prospect": prospect,
                "p_evidence": evidence,
                "p_ingest_key": ingest_key,
                "p_identity_keys": identity_keys,
            },
        )
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict):
            raise ProspectIngestError(
                "canonical prospect writer returned invalid response"
            )
        return dict(result)
