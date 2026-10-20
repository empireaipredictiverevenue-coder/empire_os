"""Local immutable knowledge versioning and audited management read regression."""
from datetime import datetime, timedelta, timezone
import os

import pytest

from empire_os.inbound_knowledge_store import OfflineKnowledgeRepository
from empire_os.inbound_tenant_knowledge import (
    KnowledgeFact, TenantKnowledgePack, answer_from_knowledge,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def pack(version=1, *, tenant="alpha", synthetic=False,
         approved=True, activated=False, answer="We fit solar panels."):
    return TenantKnowledgePack(
        tenant_id=tenant, business_name="Alpha Solar",
        version=version, activated=activated,
        facts=(KnowledgeFact(
            tenant_id=tenant, fact_id="solar-services",
            question="Do you fit solar panels",
            answer=answer,
            source_ref="reviewed-client-knowledge-v1",
            reviewed_by="client-operator-a",
            reviewed_at=(NOW - timedelta(days=1)).isoformat(),
            expires_at=(NOW + timedelta(days=30)).isoformat(),
            topic="services", approved=approved, synthetic=synthetic,
        ),),
    )


def test_explicit_activation_and_persistent_readonly_version(tmp_path):
    path = tmp_path / "knowledge.db"
    with OfflineKnowledgeRepository(path) as repo:
        assert repo.store_draft_offline(pack())
        assert not repo.store_draft_offline(pack())
        assert repo.get_active("alpha") is None
        repo.activate_offline("alpha", 1, as_of=NOW)
        active = repo.get_active("alpha")
        assert active.version == 1 and active.activated
        assert repo.active_summary("alpha")["approved_facts"] == 1
        result = answer_from_knowledge(active, "Do you fit solar panels", as_of=NOW)
        assert result.status == "approved_fact"
    with OfflineKnowledgeRepository(path, read_only=True) as repo:
        assert repo.get_active("alpha").version == 1
        assert repo.get_active("beta") is None
        assert not repo.active_summary("alpha")["customer_contact_authorized"]
        with pytest.raises(ValueError, match="read_only"):
            repo.store_draft_offline(pack(2))


def test_version_immutability_and_explicit_upgrade(tmp_path):
    path = tmp_path / "knowledge.db"
    with OfflineKnowledgeRepository(path) as repo:
        repo.store_draft_offline(pack())
        with pytest.raises(ValueError, match="conflicting"):
            repo.store_draft_offline(pack(answer="A completely different policy."))
        repo.store_draft_offline(pack(2, answer="We repair solar inverters."))
        repo.activate_offline("alpha", 1, as_of=NOW)
        assert repo.get_active("alpha").version == 1
        repo.activate_offline("alpha", 2, as_of=NOW)
        assert repo.get_active("alpha").version == 2
        assert repo.get_version("alpha", 1).version == 1


def test_unapproved_synthetic_and_empty_facts_cannot_activate(tmp_path):
    path = tmp_path / "knowledge.db"
    with OfflineKnowledgeRepository(path) as repo:
        repo.store_draft_offline(pack(1, synthetic=True))
        repo.store_draft_offline(pack(2, approved=False))
        empty = TenantKnowledgePack(
            "alpha", "Alpha Solar", 3, (),
            activated=False,
        )
        repo.store_draft_offline(empty)
        for version in (1, 2, 3):
            with pytest.raises(ValueError, match="knowledge_"):
                repo.activate_offline("alpha", version, as_of=NOW)
        assert repo.get_active("alpha") is None


def test_activated_pack_cannot_be_bypassed_during_ingestion(tmp_path):
    with OfflineKnowledgeRepository(tmp_path / "know.db") as repo:
        with pytest.raises(ValueError, match="separate_review"):
            repo.store_draft_offline(pack(activated=True))


def test_missing_readonly_store_does_not_create_file(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="existing_knowledge"):
        OfflineKnowledgeRepository(path, read_only=True)
    assert not path.exists()


def test_cross_tenant_versions_never_mix(tmp_path):
    with OfflineKnowledgeRepository(tmp_path / "know.db") as repo:
        repo.store_draft_offline(pack(tenant="alpha"))
        repo.store_draft_offline(pack(tenant="beta"))
        repo.activate_offline("alpha", 1, as_of=NOW)
        assert repo.get_active("beta") is None
        assert repo.active_summary("beta")["approved_facts"] == 0
        repo.activate_offline("beta", 1, as_of=NOW)
        assert repo.get_active("beta").tenant_id == "beta"


def test_tampered_version_detected(tmp_path):
    path = tmp_path / "know.db"
    with OfflineKnowledgeRepository(path) as repo:
        repo.store_draft_offline(pack())
        repo.db.execute("UPDATE knowledge_versions SET facts_json='[]' WHERE tenant_id='alpha'")
        repo.db.commit()
        with pytest.raises(ValueError, match="integrity_failure"):
            repo.get_version("alpha", 1)


def test_cli_reads_only_approved_source_without_provider_calls(tmp_path):
    import json
    import subprocess
    import sys

    path = tmp_path / "knowledge.db"
    with OfflineKnowledgeRepository(path) as repo:
        repo.store_draft_offline(pack())
        repo.activate_offline("alpha", 1, as_of=NOW)
    before = path.stat().st_size
    command = [
        sys.executable, "-B", "-m", "scripts.review_inbound_knowledge_20261020",
        "--knowledge-db", str(path), "--tenant-id", "alpha",
        "--question", "Do you fit solar panels", "--as-of", NOW.isoformat(),
        "--read-only",
    ]
    proc = subprocess.run(command, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "approved_fact"
    assert result["evidence_refs"] == ["reviewed-client-knowledge-v1"]
    assert result["customer_contact_authorized"] is False
    assert path.stat().st_size == before
    command[command.index("alpha")] = "beta"
    proc_other = subprocess.run(command, capture_output=True, text=True)
    assert proc_other.returncode == 0
    assert json.loads(proc_other.stdout)["status"] == "no_approved_version"
