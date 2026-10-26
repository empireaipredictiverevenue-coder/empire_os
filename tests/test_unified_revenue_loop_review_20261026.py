"""One original system review must fail closed, never trigger execution."""
from copy import deepcopy
import pytest

from scripts.review_unified_revenue_loop_20261026 import report


def payloads():
    supervisor = {
        "mode": "OBSERVE", "execution_authority": "none",
        "next_action": "continue_existing_research",
        "cross_system_cohesion": {
            "execution_authority": "NONE",
            "sources": {"x"+str(i): {"status": "CURRENT_OBSERVATION"}
                        for i in range(9)},
            "lifecycle_handoff_gates": [{} for _ in range(12)],
            "emails_sent": False, "db_writes": False,
            "payments_executed": False,
            "fully_verified_commercial_loop": False,
            "crm_tenant_link_verified_in_this_reader": False,
            "evidence_population_counts": {"recognized_revenue_cents": 0},
        },
        "canonical_opportunity_handoffs": {
            "execution_authority": "NONE",
            "records_reviewed": 18, "handoff_ready_count": 0,
            "items": [{"next_action": "COMPLETE_REAL_FACTORY_VALIDATION"}],
            "database_writes": False, "outbound_authorized": False,
        }
    }
    relationships = {
        "outbound_authorized": False,
        "buyer_evidence_brain": {
            "execution_authority": "NONE",
            "database_writes": False, "new_emails_sent": False,
            "buyer_capacity_evidence": {"status": "NO_VERIFIED_COMMERCIAL_CAPACITY"},
            "publisher_reviewed_count": 3,
            "commercial_proof_task_count": 0,
        },
    }
    return supervisor, relationships


def test_unified_original_three_changes_have_one_report_without_authority():
    r = report(*payloads())
    assert r["factory_records_reviewed"] == 18
    assert r["source_snapshots_current"] == 9
    assert r["lifecycle_stage_count"] == 12
    assert r["buyer_capacity_status"] == "NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert r["next_factory_handoff_action"] == "COMPLETE_REAL_FACTORY_VALIDATION"
    assert not r["commercial_loop_verified"]
    assert not r["canonical_tenant_link_verified"]
    assert not r["database_writes"]
    assert not r["outbound_sent"]
    assert not r["payments_executed"]


@pytest.mark.parametrize("mutate", [
    lambda s,r: s.update(mode="EXECUTE"),
    lambda s,r: s["cross_system_cohesion"].update(db_writes=True),
    lambda s,r: s["cross_system_cohesion"].update(payments_executed=True),
    lambda s,r: s["canonical_opportunity_handoffs"].update(outbound_authorized=True),
    lambda s,r: r["buyer_evidence_brain"].update(new_emails_sent=True),
    lambda s,r: r.update(outbound_authorized=True),
    lambda s,r: s["cross_system_cohesion"].update(sources={}),
    lambda s,r: s["canonical_opportunity_handoffs"].update(records_reviewed=None),
])
def test_unified_review_rejects_untrusted_or_incomplete_source(mutate):
    s,r=payloads()
    mutate(s,r)
    with pytest.raises(ValueError):
        report(s,r)
