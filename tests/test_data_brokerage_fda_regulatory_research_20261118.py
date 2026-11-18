"""OpenFDA source/packaging regression: authority, sampling, privacy and fail-closed."""
from __future__ import annotations
import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from empire_os import data_brokerage_enterprise_feed as feed
from empire_os import data_brokerage_fda_regulatory_research as fda
from empire_os import data_brokerage_enterprise_packaging as packs

NOW = datetime(2026, 11, 18, 12, 10, tzinfo=timezone.utc)
SOURCE = "us_fda_regulatory_enforcement_sample"
VIEW = "us_fda_regulatory_enforcement_landscape"

def item(n, classification="Class II"):
    return {
        "recall_number": "H-" + str(n).zfill(4) + "-2027",
        "report_date": "20261111",
        "classification": classification,
        "event_id": "X" + str(n),
        "product_type": "Food",
        "recall_initiation_date": "20261101",
        "recalling_firm": "ACME FDA Example LLC",
        "address_1": "SECRET ADDRESS: OMIT",
        "address_2": "SECRET ADDRESS 2: OMIT",
        "postal_code": "SECRET POSTCODE",
        "contact": "PERSONAL EMAIL",
        "city": "Private City",
        "state": "CA",
        "country": "United States",
        "product_description": "=DANGEROUS_FORMULA",
        "reason_for_recall": "Publisher published product-quality problem",
        "openfda": {"gmdn_term": "UNLICENSED_GMDN"},
    }

def response():
    return {
        "meta": {"last_updated": "2026-11-11", "results": {"total": 29609}},
        "results": [item(i) for i in range(400)]
    }

class RegulatoryFeedTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.state = self.root/"source.json"
        self.view_state = self.root/"view.json"

    def fetch(self):
        with patch.object(fda, "_bounded_fda_json", return_value=response()) as api:
            rows,url,meta = fda.fetch_research_sample(NOW.isoformat())
        self.assertEqual(api.call_count, 3)
        return rows,url,meta

    def test_three_official_sectors_bounded_and_provenance(self):
        rows,url,meta = self.fetch()
        self.assertEqual(len(rows), 1200)
        self.assertEqual({r["sector"] for r in rows}, set(fda.ENDPOINTS))
        self.assertEqual(len({r["record_id"] for r in rows}),1200)
        self.assertEqual(meta["source_network_requests"],3)
        self.assertEqual(meta["publisher_last_updated_by_sector"]["food"],"2026-11-11")
        self.assertIn("RESEARCH_NOT_RECALL",meta["source_policy"])
        self.assertEqual(meta["publisher_total_reported_by_sector"]["device"],29609)
        for r in rows:
            self.assertNotIn("address_1",r)
            self.assertNotIn("contact",r)
            self.assertNotIn("openfda",r)
            self.assertNotIn("GMDN",r["published_product_summary"])
            self.assertEqual(r["company_identity_verified"],"false")
            self.assertTrue(r["published_product_summary"].startswith("'="))
            self.assertEqual(r["published_corporate_name_candidate"],"ACME FDA Example LLC")
        self.assertEqual(url,"https://open.fda.gov/apis/")

    def test_no_unreviewed_personal_company_name(self):
        r=item(1)
        r["recalling_firm"]="Jane Example"
        out=fda._validate_enforcement_record(r, "food", NOW.isoformat())
        self.assertEqual(out["published_corporate_name_candidate"],"")
        self.assertNotIn("Jane",str(out))

    def test_missing_and_na_recall_ids_are_quarantined(self):
        doc = response()
        doc["results"][0]["recall_number"] = "N/A"
        doc["results"][1]["recall_number"] = ""
        with patch.object(fda,"_bounded_fda_json",return_value=doc):
            rows,_,meta=fda.fetch_research_sample(NOW.isoformat())
        self.assertEqual(len(rows),1194)
        self.assertEqual(meta["excluded_missing_or_na_recall_id_by_sector"],
                         {sector:2 for sector in fda.ENDPOINTS})
        self.assertEqual(meta["source_records_accepted"],1194)
        self.assertEqual(meta["source_records_returned_by_publisher"],1200)

    def test_invalid_classification_fails(self):
        with self.assertRaisesRegex(ValueError,"CLASSIFICATION"):
            fda._validate_enforcement_record(item(1,"Class 9"), "food", NOW.isoformat())

    def test_invalid_fda_page_fails_without_partial_output(self):
        partial=response()
        partial["results"]=partial["results"][:399]
        with patch.object(fda,"_bounded_fda_json",return_value=partial):
            with self.assertRaisesRegex(ValueError,"PAGE_INCOMPLETE"):
                fda.fetch_research_sample(NOW.isoformat())
        self.assertEqual(list(self.data.glob("*.csv")),[])

    def test_fda_owner_live_research_and_packaging_without_release(self):
        rows,url,meta=self.fetch()
        with patch.object(feed,"SOURCES",{SOURCE:feed.SOURCES[SOURCE]}):
            source=feed.run_due(self.root,now=NOW,allow_noncanonical=True,
                     dataset_root=self.data,state_path=self.state,
                     fetchers={SOURCE:lambda _: (rows,url,meta)})
        self.assertEqual(source["status"],"VERIFIED_CHANGED")
        self.assertEqual(source["records"],1200)
        self.assertEqual(source["network_requests"],3)
        source_state=json.loads(self.state.read_text())
        self.assertFalse(source_state["source_redistribution_approved"])
        self.assertEqual(source_state["datasets"][SOURCE]["publisher_publication_metadata"]["window_latest_report_date"],"2026-11-11")
        with patch.object(packs,"VIEWS",{VIEW:packs.VIEWS[VIEW]}):
            view=packs.run_due(self.root,now=NOW,allow_noncanonical=True,
                source_state_path=self.state,state_path=self.view_state,
                dataset_root=self.data)
        self.assertEqual(view["status"],"VIEW_VERIFIED_INTERNAL")
        self.assertEqual(view["view_records"],3)
        result=json.loads(self.view_state.read_text())
        self.assertFalse(result["customer_delivery_authorized"])
        self.assertFalse(result["sales_authorized"])
        self.assertFalse(result["views"][VIEW]["resale_licence_cleared"])
        with (self.data/(VIEW+".csv")).open() as handle:
            rows=list(csv.DictReader(handle))
        self.assertEqual(sum(int(r["distinct_reports_in_sample"]) for r in rows),1200)
        self.assertEqual({r["sector"] for r in rows},set(fda.ENDPOINTS))
        self.assertTrue(all(r["evidence_flag"].endswith("SAFETY_ALERT") for r in rows))

    def test_failclosed_duplicate_recall_ids(self):
        bad=response()
        bad["results"][-1]=bad["results"][0]
        with patch.object(fda,"_bounded_fda_json",return_value=bad):
            with self.assertRaisesRegex(ValueError,"DUPLICATE_RECALL_ID"):
                fda.fetch_research_sample(NOW.isoformat())

if __name__ == "__main__":
    unittest.main(verbosity=2)
