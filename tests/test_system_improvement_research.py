"""Fail-closed research-first System Improvement Agent contract."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import empire_os.system_improvement_research as research


def _registry():
    def row(key, n):
        return {
            "key": key, "name": n, "owner": "engineering",
            "checklist_pending": 2, "checklist_done": 1,
            "module_evidence": [f"empire_os/{key}.py"],
            "pending_items": ["prove production result"],
        }
    return {"workstreams": [
        row("opportunity_factory", "Opportunity Factory / Evidence"),
        row("buyer_acquisition", "Buyer Acquisition"),
    ]}


def test_research_three_real_phases_and_distinct_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(
        research, "build_completion_capability_registry", lambda root: _registry()
    )
    (tmp_path / "empire_os").mkdir()
    (tmp_path / "empire_os/opportunity_factory.py").write_text("pass\n")
    calls = []
    def search(query, *, num):
        calls.append(query)
        assert num == 3
        i = len(calls)
        return {"organic": [{
            "title": f"Official source {i}",
            "link": (
                f"https://www.nist.gov/doc/{i}" if i % 2
                else f"https://www.w3.org/standards/{i}"
            ),
        }]}
    t = datetime(2026, 10, 9, tzinfo=timezone.utc)
    def inspect(url):
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "source_url": url,
            "document_headings": ["Relevant official standard"],
            "content_sha256": "0" * 64,
            "publication_date_verified": False,
            "claim_accuracy_verified": False,
        }
    for index in range(3):
        x = research.research_once(
            tmp_path, search_fn=search, source_inspector=inspect,
            now=t + timedelta(minutes=40 * index),
        )
        assert x["searches_executed"] == 1
        assert x["mode"] == "OBSERVE"
        assert x["auto_code_edits"] is False
    d = research.load(
        tmp_path / research.OUTPUT / "dossiers/opportunity_factory.json"
    )
    assert d["status"] == "ORIGINAL_SOURCES_CHECKED_REVIEW_REQUIRED"
    assert d["primary_source_pages_checked"] == 2
    assert d["source_count"] == 3
    assert d["independent_domain_count"] == 2
    assert len(d["phases"]) == 3
    assert d["production_change_authorized"] is False
    assert all(s["retrieved_page_verified"] is True
               for s in d["citations_to_inspect"])
    assert d["audit"]["runtime_verification"] == "NOT_PROVED_BY_CODE_INVENTORY"
    assert d["audit"]["source_module_count"] == 1
    coverage = research.load(tmp_path / research.OUTPUT / "coverage_latest.json")
    assert coverage["workstream_count"] == 2
    assert coverage["research_complete_for_review"] == 1
    assert coverage["workstreams"][0]["production_completion"] == "NOT_ATTESTED_BY_RESEARCH"
    report_text = (tmp_path / research.OUTPUT / "dossiers/opportunity_factory.md").read_text()
    assert "Original" not in report_text or "original headings inspected" in report_text
    assert "No commercial action" in report_text
    next_result = research.research_once(
        tmp_path, search_fn=search, now=t + timedelta(minutes=130),
    )
    assert next_result["research_steps"][0]["workstream"] == "buyer_acquisition"
    assert len(calls) == 4


def test_cooldown_prevents_duplicate_research_queries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        research, "build_completion_capability_registry", lambda root: _registry()
    )
    calls = []
    def search(query, *, num):
        calls.append(query)
        return {"organic": []}
    t = datetime(2026, 10, 9, tzinfo=timezone.utc)
    research.research_once(tmp_path, search_fn=search, now=t)
    result = research.research_once(
        tmp_path, search_fn=search, now=t + timedelta(minutes=10)
    )
    assert result["status"] == "COOLDOWN"
    assert result["searches_executed"] == 0
    assert len(calls) == 1
    assert result["execution_authority"] == "none"


def test_research_does_not_invent_sources_on_provider_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        research, "build_completion_capability_registry", lambda root: _registry()
    )
    def fail(query, *, num):
        raise TimeoutError("provider secret=neverprint")
    result = research.research_once(
        tmp_path, search_fn=fail, force=True, max_queries=3,
    )
    d = research.load(
        tmp_path / research.OUTPUT / "dossiers/opportunity_factory.json"
    )
    assert result["searches_executed"] == 3
    assert d["source_count"] == 0
    # Three failed attempts exhaust only phase 1; the agent must not
    # pretend that phases 2 and 3 were researched.
    assert d["status"] == "RESEARCH_INCOMPLETE"
    assert sum(value is not None for value in d["phases"].values()) == 1
    assert d["phases"]["official_standards"]["attempt_count"] == 3
    assert d["phases"]["official_standards"]["provider_degraded"] is True
    assert "neverprint" not in json.dumps(result)
    assert "neverprint" not in json.dumps(d)
    assert d["funds_authorized"] is False


def test_untrusted_or_internal_citations_are_rejected():
    for candidate in (
        {"title": "private", "url": "http://localhost/admin"},
        {"title": "loopback", "url": "https://127.0.0.1/private"},
        {"title": "root", "url": "file:///etc/shadow"},
        {"title": "credential", "url": "https://user:secret@host.test/"},
        {"title": "", "url": "https://www.nist.gov/foo"},
    ):
        assert research.citation(candidate) is None
    good = research.citation({
        "title": "NIST AI RMF",
        "link": "https://www.nist.gov/itl/ai-risk-management-framework?q=x",
    })
    assert good["url"].endswith("/itl/ai-risk-management-framework")
    assert good["supports_business_outcome"] is False


def test_registry_uses_all_real_workstreams():
    root = Path(__file__).resolve().parents[1]
    registry = research.build_completion_capability_registry(root)
    assert len(registry["workstreams"]) == 31
    assert {"opportunity_factory", "revenue_truth", "search_intelligence"}.issubset(
        {x["key"] for x in registry["workstreams"]}
    )


def test_primary_inspection_never_fetches_nonofficial_sites(monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("no network for unapproved host")
    monkeypatch.setattr(research, "build_opener", deny_network)
    result = research.inspect_primary_page("https://untrusted.example.org/foo")
    assert result["status"] == "DISCOVERY_SOURCE_NOT_PRIMARY"
    local = research.inspect_primary_page("https://localhost/private")
    assert local["status"] == "UNSAFE_URL_REJECTED"


def test_primary_inspection_extracts_original_document_headings(monkeypatch):
    class Headers:
        def get_content_type(self):
            return "text/html"
    class Response:
        headers = Headers()
        def read(self, size):
            return (b"<html><head><title>Original official guidance</title></head>"
                    b"<body><h1>Measure risks</h1><h2>Manage controls</h2></body>"
                    b"</html>")
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
    class Opener:
        def open(self, req, timeout):
            assert timeout == 5
            assert req.full_url.startswith("https://www.nist.gov/")
            return Response()
    monkeypatch.setattr(research, "build_opener", lambda *args: Opener())
    result = research.inspect_primary_page("https://www.nist.gov/itl/ai-risk-management-framework")
    assert result["status"] == "ORIGINAL_HTML_HEADINGS_INSPECTED"
    assert "Measure risks" in result["document_headings"]
    assert "Manage controls" in result["document_headings"]
    assert result["publication_date_verified"] is False
    assert result["claim_accuracy_verified"] is False
    assert len(result["content_sha256"]) == 64
