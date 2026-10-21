"""Guard Quora as owned SEO support, not unapproved call source or backlinks."""
from __future__ import annotations
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/seo/LEAD_SMART_QUORA_ANSWER_REVIEW_QUEUE_20261021.csv"
AUDIT = ROOT / "docs/seo/EMPIRE_SEARCH_SYSTEM_REUSE_AUDIT_20261021.md"


def test_unpublished_quora_queue_is_review_only_and_source_safe():
    with QUEUE.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 8
    assert len({r["item_id"] for r in rows}) == len(rows)
    assert all(r["answer_status"] == "RESEARCH_ONLY" for r in rows)
    assert all(r["owner_review"] == "REQUIRED" for r in rows)
    assert all(r["quora_account_verified"] == "false" for r in rows)
    assert all(r["actual_quora_question_url"] == "" for r in rows)
    assert all(r["link_approved"] == "false" for r in rows)
    assert all(r["seo_page_public_verified"] == "false" for r in rows)
    assert all(r["seo_page"].startswith("/roofing") for r in rows)


def test_existing_search_engine_and_traffic_constraints_are_not_reinvented():
    audit = AUDIT.read_text(encoding="utf-8")
    assert "empire_os/search_fabric/" in audit
    assert "empire_os/search_intelligence/" in audit
    assert "EmpireDB PostgreSQL" in audit
    assert "EMPIRE_FIRST_PARTY_ORGANIC" in audit
    assert "No automated posting" in audit
    assert "HTTP 405" in audit
