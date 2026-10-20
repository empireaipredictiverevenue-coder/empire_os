"""Local immutable-version tenant knowledge repository with explicit activation.

NOT a live content management system. Local ingestion and activation require
an operator-controlled Python context; no public write endpoint is exposed.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from empire_os.inbound_tenant_knowledge import KnowledgeFact, TenantKnowledgePack, _utc


class OfflineKnowledgeRepository:
    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if read_only:
            if not self.path.is_file() or self.path.is_symlink():
                raise ValueError("existing_knowledge_database_required")
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.execute("PRAGMA query_only = ON")
        else:
            if self.path != Path(":memory:") and (
                not self.path.parent.is_dir() or self.path.is_symlink()
            ):
                raise ValueError("invalid_knowledge_store_path")
            self.db = sqlite3.connect(str(self.path))
            self.db.execute("PRAGMA foreign_keys = ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_versions (
                    tenant_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    business_name TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, version)
                );
                CREATE TABLE IF NOT EXISTS active_knowledge (
                    tenant_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    FOREIGN KEY (tenant_id, version)
                        REFERENCES knowledge_versions(tenant_id, version)
                );
            """)

    def __enter__(self) -> "OfflineKnowledgeRepository":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.db.close()

    @staticmethod
    def _serialized_facts(pack: TenantKnowledgePack) -> str:
        return json.dumps([asdict(f) for f in pack.facts],
                          sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def store_draft_offline(self, pack: TenantKnowledgePack) -> bool:
        if self.read_only:
            raise ValueError("knowledge_database_read_only")
        if pack.activated:
            raise ValueError("knowledge_activation_requires_separate_review")
        body = self._serialized_facts(pack)
        digest = sha256(body.encode("utf-8")).hexdigest()
        with self.db:
            existing = self.db.execute(
                "SELECT business_name,content_sha256 FROM knowledge_versions "
                "WHERE tenant_id=? AND version=?",
                (pack.tenant_id, pack.version),
            ).fetchone()
            if existing:
                if existing != (pack.business_name, digest):
                    raise ValueError("conflicting_knowledge_version")
                return False
            self.db.execute(
                "INSERT INTO knowledge_versions "
                "(tenant_id,version,business_name,facts_json,content_sha256) "
                "VALUES (?,?,?,?,?)",
                (pack.tenant_id, pack.version, pack.business_name, body, digest),
            )
        return True

    def get_version(self, tenant_id: str, version: int) -> TenantKnowledgePack | None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        row = self.db.execute(
            "SELECT business_name,facts_json,content_sha256 FROM knowledge_versions "
            "WHERE tenant_id=? AND version=?", (tenant_id, version),
        ).fetchone()
        if not row:
            return None
        if sha256(row[1].encode("utf-8")).hexdigest() != row[2]:
            raise ValueError("knowledge_version_integrity_failure")
        entries = json.loads(row[1])
        if not isinstance(entries, list):
            raise ValueError("invalid_knowledge_version")
        return TenantKnowledgePack(
            tenant_id=tenant_id, version=version, business_name=row[0],
            facts=tuple(KnowledgeFact(**entry) for entry in entries),
            activated=False,
        )

    def activate_offline(self, tenant_id: str, version: int, *, as_of: datetime) -> None:
        if self.read_only:
            raise ValueError("knowledge_database_read_only")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("activation_timestamp_requires_timezone")
        candidate = self.get_version(tenant_id, version)
        if candidate is None:
            raise ValueError("knowledge_version_not_found")
        if not candidate.facts:
            raise ValueError("knowledge_pack_empty")
        if any(
            not f.approved or f.synthetic
            or not _utc(f.reviewed_at) <= as_of < _utc(f.expires_at)
            for f in candidate.facts
        ):
            raise ValueError("knowledge_activation_requires_current_real_approval")
        with self.db:
            self.db.execute(
                "INSERT INTO active_knowledge (tenant_id,version) VALUES (?,?) "
                "ON CONFLICT(tenant_id) DO UPDATE SET version=excluded.version",
                (tenant_id, version),
            )

    def get_active(self, tenant_id: str) -> TenantKnowledgePack | None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id_required")
        record = self.db.execute(
            "SELECT version FROM active_knowledge WHERE tenant_id=?",
            (tenant_id,),
        ).fetchone()
        if record is None:
            return None
        draft = self.get_version(tenant_id, record[0])
        if draft is None:
            raise ValueError("missing_active_knowledge_version")
        return TenantKnowledgePack(
            tenant_id=draft.tenant_id, business_name=draft.business_name,
            version=draft.version, facts=draft.facts, activated=True,
        )

    def active_summary(self, tenant_id: str) -> dict:
        active = self.get_active(tenant_id)
        return {
            "tenant_id": tenant_id,
            "status": "approved_version_available" if active else "no_approved_version",
            "active_version": active.version if active else None,
            "approved_facts": sum(1 for f in active.facts if f.approved and not f.synthetic)
            if active else 0,
            "customer_contact_authorized": False,
            "live_knowledge_serving_enabled": False,
        }
