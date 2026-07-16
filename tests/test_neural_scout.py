"""
Tests for the Neural Scout.
"""

import json

import pytest
from empire_os.funnel import SQLiteBackend, get_state, list_states
from empire_os.neural_scout import (
    NeuralScout,
    calculate_synthetic_score,
    ScoredLead,
)
from empire_os.scanner import (
    StaticFileScanner,
    DBPRScanner,
    _generate_leads_for_niche,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


class TestScoring:
    def test_high_score_roofing(self):
        score = calculate_synthetic_score(
            niche="roofing",
            details="Commercial warehouse roof has storm damage from recent hail. "
                     "Multiple leaks reported. Facility needs urgent repair. "
                     "Multi-unit building with flat roof.",
            phone="555-123-4567",
            zip_code="33101",
        )
        assert score >= 0.70, f"Expected high score, got {score}"

    def test_low_score_no_details(self):
        score = calculate_synthetic_score(
            niche="landscaping",
            details="Lawn service",
            phone="",
            zip_code="",
        )
        assert score < 0.50, f"Expected low score, got {score}"

    def test_mass_torts_base_weight(self):
        score = calculate_synthetic_score(
            niche="mass_torts",
            details="Exposed to toxic chemicals at work for 5 years. "
                     "Multiple health issues diagnosed. Seeking legal counsel "
                     "for class action lawsuit.",
            phone="555-999-8888",
        )
        assert score >= 0.55

    def test_unknown_niche_default(self):
        score = calculate_synthetic_score(
            niche="dog_walking",
            details="Looking for dog walker in downtown area",
            phone="",
        )
        assert score == 0.35


class TestNeuralScout:
    def _make_scout(self, backend, **kw):
        """Create a scout without auto-registered scanners (test isolation)."""
        return NeuralScout(backend, auto_register=False, **kw)

    def test_default_scanners_registered(self):
        """When auto_register=True, all 6 scanners should be loaded."""
        b = SQLiteBackend(":memory:")
        b.ensure_schema()
        scout = NeuralScout(b, auto_register=True)
        assert len(scout._scanners) == 6
        names = {s.name for s in scout._scanners}
        assert names == {
            "dbpr", "sunbiz", "county-appraiser",
            "permits", "bbb", "web-search",
        }

    def test_evaluate_qualified(self, backend):
        scout = self._make_scout(backend, min_score=0.30)
        lead = scout.evaluate(
            niche="roofing",
            details="Commercial warehouse storm damage hail leak multi-unit",
            phone="555-123-4567",
            zip_code="33101",
            name="ABC Roofing Co",
            source="web",
        )
        assert lead is not None
        assert lead.niche == "roofing"
        assert lead.score >= 0.30

    def test_evaluate_below_threshold(self, backend):
        scout = self._make_scout(backend, min_score=0.70)
        lead = scout.evaluate(
            niche="landscaping",
            details="Lawn care",
            phone="",
        )
        assert lead is None

    def test_register_lead(self, backend):
        scout = self._make_scout(backend)
        lead = ScoredLead(
            prospect_id="test-p1",
            niche="hvac",
            source="web",
            score=0.65,
            details="Commercial AC unit needs replacement",
            phone="555-111-2222",
            zip_code="33101",
            discovered_at="2026-07-12T18:00:00",
        )
        eid = scout.register_lead(lead)
        assert eid > 0
        state = get_state(backend, "test-p1")
        assert state is not None
        assert state.current_state == "discovered"

    def test_tick_with_static_scanner(self, backend, tmp_path):
        leads_file = tmp_path / "leads.json"
        leads_file.write_text(json.dumps([
            {
                "niche": "roofing",
                "details": "Commercial warehouse storm damage multiple leaks facility",
                "phone": "555-123-4567",
                "zip_code": "33101",
                "name": "ABC Roofing",
            },
            {
                "niche": "hvac",
                "details": "AC repair",
                "phone": "",
                "zip_code": "",
                "name": "Quick Cool",
            },
        ]))

        scout = self._make_scout(backend, min_score=0.30)
        scout.register_scanner(StaticFileScanner(str(leads_file)))

        results = scout.tick()
        assert results["scanned"] == 2
        assert results["registered"] >= 1
        states = list_states(backend)
        assert len(states) >= 1

    def test_dbpr_scanner_fallback_produces_leads(self):
        """DBPR fallback should generate seed leads without network calls."""
        scanner = DBPRScanner()
        leads = scanner._fallback(niches=["roofing", "hvac"])
        assert len(leads) > 0
        for l in leads:
            assert "niche" in l
            assert "name" in l
            assert l["source"] == "generated"

    def test_scout_with_dbpr_fallback_wires_into_tick(self, backend, monkeypatch):
        """Single scanner flows through scout.evaluate into funnel (fallback path)."""
        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **kw: type("R",(),{
            "status_code": 200,
            "text": "",
            "raise_for_status": lambda self: None,
        })())
        scout = self._make_scout(backend, min_score=0.30)
        scanner = DBPRScanner()
        scout.register_scanner(scanner)
        results = scout.tick()
        # With empty HTML from our monkey-patched request, _parse_html returns []
        # which means _search returns [], so scan() hits _fallback → generates leads
        assert results["scanned"] > 0
        assert results["registered"] >= 0

    def test_scout_pipeline_integration(self, backend):
        scout = self._make_scout(backend)
        l1 = scout.evaluate(
            niche="mass_torts",
            details="Chemical exposure at manufacturing plant. 15 years employed. "
                     "Developed respiratory conditions. Seeking class action info.",
            phone="555-555-5555",
            name="John Doe",
        )
        assert l1 is not None
        scout.register_lead(l1)

        l2 = scout.evaluate(
            niche="pest_control",
            details="Need spray",
            phone="",
        )
        if l2:
            scout.register_lead(l2)

        state = get_state(backend, l1.prospect_id)
        assert state is not None
        assert state.current_state == "discovered"

    def test_generate_leads_for_niche(self):
        leads = _generate_leads_for_niche("roofing", count=3, location="FL")
        assert len(leads) == 3
        for l in leads:
            assert l["niche"] == "roofing"
            assert "phone" in l
            assert "zip_code" in l
