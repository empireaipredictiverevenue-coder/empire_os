"""Tests for the registry scraper."""
from unittest.mock import patch, MagicMock

import pytest
from empire_os.registry_scraper import (
    RegistryScraper, RegistryRecord, RegistryResult,
)


BBB_HTML = """
<html>
<body>
<div class="result-item">
  <div>
    <h3>Acme Roofing LLC</h3>
    <p>(555) 123-4567</p>
    <p class="bds-css-address">123 Main St, Tampa, FL 33602</p>
  </div>
</div>
<div class="result-item">
  <div>
    <h3>Acme Roofing Inc</h3>
    <p>(555) 987-6543</p>
  </div>
</div>
</body>
</html>
"""


class TestRegistryScraper:
    def test_search_no_company(self):
        s = RegistryScraper(rate_limit_seconds=0)
        result = s.search("")
        assert result.error == "no company name"

    def test_search_returns_results_from_mocked_bbb(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_fetch", return_value=BBB_HTML):
            result = s.search("Acme Roofing")
        # Should find at least the first Acme Roofing LLC record
        companies = [r.company_name for r in result.records]
        assert any("Acme Roofing" in c for c in companies)
        assert "bbb" in result.sources_tried

    def test_search_records_phone(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_fetch", return_value=BBB_HTML):
            result = s.search("Acme Roofing")
        phones = [r.phone for r in result.records if r.phone]
        assert any("555" in p for p in phones)

    def test_search_handles_no_results(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_fetch", return_value=None):
            result = s.search("NoSuchCompany")
        assert result.records == []
        assert "bbb" in result.sources_tried  # still tried

    def test_search_handles_fetch_error(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_fetch", side_effect=RuntimeError("network down")):
            result = s.search("Acme")
        # Should not crash; should record empty
        assert isinstance(result.records, list)

    def test_best_returns_highest_confidence(self):
        s = RegistryScraper(rate_limit_seconds=0)
        result = RegistryResult(records=[
            RegistryRecord(company_name="A", confidence=0.5),
            RegistryRecord(company_name="B", confidence=0.9),
            RegistryRecord(company_name="C", confidence=0.7),
        ])
        assert result.best.company_name == "B"

    def test_best_returns_none_when_empty(self):
        result = RegistryResult()
        assert result.best is None

    def test_sunbiz_skipped_outside_fl(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_search_bbb", return_value=[]), \
             patch.object(s, "_search_sunbiz") as mock_sunbiz:
            s.search("Acme", state="CA")
        mock_sunbiz.assert_not_called()

    def test_sunbiz_called_for_fl(self):
        s = RegistryScraper(rate_limit_seconds=0)
        with patch.object(s, "_search_bbb", return_value=[]), \
             patch.object(s, "_search_sunbiz", return_value=RegistryRecord(
                 company_name="Acme LLC", state="FL", source="sunbiz", confidence=0.95)):
            result = s.search("Acme", state="FL")
        assert "sunbiz" in result.sources_tried
        assert len(result.records) == 1


class TestRegistryRecord:
    def test_defaults(self):
        r = RegistryRecord()
        assert r.company_name == ""
        assert r.confidence == 0.0

    def test_to_dict(self):
        r = RegistryRecord(company_name="Acme", state="FL", confidence=0.9)
        d = r.to_dict()
        assert d["company_name"] == "Acme"
        assert d["state"] == "FL"
        assert d["confidence"] == 0.9