"""Canonical Search Intelligence expands Quora into multiple verticals without new execution authority."""
import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.quora_intelligence import (
    EXPANSION_QUEUE, QUEUE, QuoraEvidenceError, read_topic_queue, review_quora_research
)
from empire_os.search_intelligence.service import build_search_intelligence_service

COUNTS = {"roofing": 16, "hvac": 8, "solar": 8, "dental": 8, "legal": 8, "b2b": 8}


def test_original_roofing_topics_remain_and_six_verticals_are_research_only():
    with QUEUE.open(newline="", encoding="utf-8") as source:
        originals = list(csv.DictReader(source))
    with EXPANSION_QUEUE.open(newline="", encoding="utf-8") as source:
        expanded = list(csv.DictReader(source))
    assert len(originals) == 8
    assert len(expanded) == 48
    all_topics = read_topic_queue()
    assert len(all_topics) == 56
    assert all_topics[:8] == tuple(originals)
    assert len({r["item_id"] for r in all_topics}) == len(all_topics)
    assert all(r["answer_status"] == "RESEARCH_ONLY" for r in all_topics)
    assert all(r["link_approved"] == "false" for r in all_topics)
    assert all(r["quora_account_verified"] == "false" for r in all_topics)
    assert all(r["actual_quora_question_url"] == "" for r in all_topics)


def test_vertical_summary_and_specialist_review_always_held():
    output = review_quora_research()
    assert output["topic_count"] == 56
    assert output["vertical_topic_counts"] == COUNTS
    assert output["verified_quora_questions"] == 0
    assert output["published_answers_verified"] == 0
    assert output["automated_posting_authorized"] is False
    assert output["third_party_visits_first_party"] is False
    assert output["buyer_accepted_calls_verified"] is False
    assert output["execution_authority"] == "NONE"
    assert all(t["specialist_editorial_review_required"]
               for t in output["topics"] if t["vertical"] in {"dental", "legal"})
    assert all(not t["specialist_editorial_review_required"]
               for t in output["topics"] if t["vertical"] in {"roofing", "hvac", "solar", "b2b"})
    assert output["expansion_topic_digest"].startswith("sha256:")


def test_search_service_exposes_updated_queue_without_publishing():
    client = TestClient(build_search_intelligence_service())
    reply = client.get("/v1/search/quora/review")
    assert reply.status_code == 200
    assert reply.headers["Cache-Control"] == "no-store"
    assert reply.json()["vertical_topic_counts"] == COUNTS
    assert len(reply.json()["topics"]) == 56
    assert reply.json()["execution_authority"] == "NONE"


def test_changed_supplemental_file_rejects_unapproved_publication(tmp_path, monkeypatch):
    import empire_os.search_intelligence.quora_intelligence as mod
    attack = tmp_path / "topics.csv"
    attack.write_bytes(EXPANSION_QUEUE.read_bytes())
    with attack.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        header = reader.fieldnames
    rows[0]["link_approved"] = "true"
    with attack.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, header)
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(mod, "EXPANSION_QUEUE", attack)
    with pytest.raises(QuoraEvidenceError, match="UNAPPROVED_OR_DUPLICATE"):
        read_topic_queue()


def test_duplicate_topic_theme_across_queue_is_rejected(tmp_path, monkeypatch):
    import empire_os.search_intelligence.quora_intelligence as mod
    attack = tmp_path / "topics.csv"
    with EXPANSION_QUEUE.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        header = reader.fieldnames
    with QUEUE.open(newline="", encoding="utf-8") as file:
        original = next(csv.DictReader(file))["question_theme"]
    rows[0]["question_theme"] = original
    with attack.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, header)
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(mod, "EXPANSION_QUEUE", attack)
    with pytest.raises(QuoraEvidenceError, match="UNAPPROVED_OR_DUPLICATE"):
        read_topic_queue()
