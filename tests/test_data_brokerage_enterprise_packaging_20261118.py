"""No-network reproducibility and commercial-release isolation tests."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from empire_os import data_brokerage_enterprise_feed as feed
from empire_os import data_brokerage_enterprise_packaging as pack

T0 = datetime(2026, 11, 18, 11, 5, tzinfo=timezone.utc)

class ProductViewTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.dataset_root = self.root/"datasets"
        self.dataset_root.mkdir()
        self.source_state_path = self.root/"enterprise_feed.json"
        self.state_path = self.root/"enterprise_products.json"
        self.source = {}
        for name in feed.SOURCES:
            if name == "us_fda_regulatory_enforcement_sample":
                continue  # Dedicated FDA source test owns its fixture.
            cols = feed.HEADERS[name]
            r = {key:"" for key in cols}
            if name == "us_disaster_declaration_activity":
                r.update(disaster_number="123",state="CA",fips_state="06",
                         fips_county="001",county_designated_area="Alameda",
                         event_type="Fire",declaration_date="2026-11-01")
            if name == "global_legal_entity_identity_gb":
                r.update(lei="984500F379A5E98DO895",entity_name="Example Limited")
            if name == "uk_renewable_development_projects":
                r.update(project_ref="1",site_name="Test Solar Farm",
                         development_status="Under Construction",capacity_mw="1.5")
            if name == "uk_cqc_corporate_care_locations":
                r.update(location_id="1-TEST",provider_id="P1",service_name="Example Healthcare",
                         service_type="Dentist",region="London",
                         local_authority="City of London",last_check_date="01/Nov/2026")
            b=feed._csv_bytes(name,[r])
            (self.dataset_root/(name+".csv")).write_bytes(b)
            self.source[name]={
                "source_status":"VERIFIED_UNCHANGED","quality_pass":True,
                "row_count":1,"source_snapshot_sha256":hashlib.sha256(b).hexdigest(),
                "source_url": ("https://www.cqc.org.uk/system/files/2026-11/04_November_2026_CQC_directory.csv"
                               if name == "uk_cqc_corporate_care_locations" else "https://source") }
        self._state()

    def _state(self):
        self.source_state_path.write_text(json.dumps({
            "schema":feed.SCHEMA,"datasets":self.source,
            "customer_delivery_authorized":False,
        }))

    def run_once(self):
        return pack.run_due(self.root,now=T0,allow_noncanonical=True,
            dataset_root=self.dataset_root,
            state_path=self.state_path,source_state_path=self.source_state_path)

    def test_bootstrap_three_views_and_noncommercial_contract(self):
        results=[self.run_once() for _ in range(3)]
        self.assertEqual([r["status"] for r in results],
                         ["VIEW_VERIFIED_INTERNAL"]*3)
        self.assertEqual([r["view_records"] for r in results],[1,1,1])
        out=json.loads(self.state_path.read_text())
        self.assertFalse(out["sales_authorized"])
        self.assertFalse(out["public_marketplace_enabled"])
        self.assertFalse(out["customer_delivery_authorized"])
        self.assertEqual(len(out["views"]),3)
        for k,v in out["views"].items():
            self.assertFalse(v["resale_licence_cleared"])
            self.assertFalse(v["customer_delivery_authorized"])
            self.assertEqual(v["status"],"VIEW_VERIFIED_INTERNAL")

    def test_dedupe_and_zero_mutation_when_current(self):
        for _ in range(3):self.run_once()
        before=self.state_path.read_bytes()
        r=self.run_once()
        self.assertEqual(r["view_writes"],0)
        self.assertEqual(self.state_path.read_bytes(),before)

    def test_upstream_digest_mismatch_holds_view(self):
        self.source["us_disaster_declaration_activity"]["source_snapshot_sha256"]="0"*64
        self._state()
        r=self.run_once()
        self.assertEqual(r["status"],"VIEW_REFRESH_HELD")
        self.assertEqual(r["view_writes"],0)
        self.assertFalse((self.dataset_root/"us_disaster_territory_activity_sample.csv").exists())

    def test_upstream_source_held_does_not_publish(self):
        self.source["us_disaster_declaration_activity"]["quality_pass"]=False
        self._state()
        r=self.run_once()
        self.assertEqual(r["view"],"uk_healthcare_territory_coverage")
        self.assertFalse((self.dataset_root/"us_disaster_territory_activity_sample.csv").exists())

    def test_snapshot_changes_rebuild_and_archive(self):
        self.run_once()
        name="us_disaster_declaration_activity"
        path=self.dataset_root/(name+".csv")
        rows=feed._read_rows_from_path(name,path)
        rows[0]["event_type"]="Hurricane"
        new=feed._csv_bytes(name,rows)
        path.write_bytes(new)
        self.source[name]["source_snapshot_sha256"]=hashlib.sha256(new).hexdigest()
        self._state()
        out=self.run_once()
        self.assertEqual(out["status"],"VIEW_VERIFIED_INTERNAL")
        self.assertEqual(len(list((self.dataset_root/"history").glob("*.csv"))),1)

    def test_verified_view_becomes_held_when_source_refresh_fails(self):
        for _ in range(3):
            self.run_once()
        src="uk_cqc_corporate_care_locations"
        self.source[src]["source_status"]="SOURCE_REFRESH_HELD"
        self.source[src]["quality_pass"]=False
        self._state()
        held=self.run_once()
        self.assertEqual(held["views_held"],1)
        d=json.loads(self.state_path.read_text())
        self.assertEqual(d["views"]["uk_healthcare_territory_coverage"]["status"],
                         "VIEW_STALE_SOURCE_HELD")
        self.assertFalse(d["views"]["uk_healthcare_territory_coverage"]["customer_delivery_authorized"])
        self.source[src]["source_status"]="VERIFIED_UNCHANGED"
        self.source[src]["quality_pass"]=True
        self._state()
        restored=self.run_once()
        self.assertEqual(restored["view"],"uk_healthcare_territory_coverage")
        self.assertEqual(restored["status"],"VIEW_VERIFIED_INTERNAL")

    def test_cqc_publisher_date_follows_official_release(self):
        self.run_once()
        self.run_once()
        path=self.dataset_root/"uk_healthcare_territory_coverage.csv"
        self.assertIn("2026-11-04",path.read_text())
        self.source["uk_cqc_corporate_care_locations"]["source_url"]=(
            "https://www.cqc.org.uk/system/files/2026-11/13_November_2026_CQC_directory.csv")
        self._state()
        changed=self.run_once()
        self.assertEqual(changed["view"],"uk_healthcare_territory_coverage")
        self.assertEqual(changed["status"],"VIEW_VERIFIED_INTERNAL")
        self.assertIn("2026-11-13",path.read_text())

    def test_noncanonical_root_held_without_write(self):
        r=pack.run_due(self.root)
        self.assertEqual(r["status"],"NONCANONICAL_ROOT_HELD")
        self.assertFalse(self.state_path.exists())

    def test_rejected_source_customer_authority(self):
        self.source_state_path.write_text(json.dumps({
            "schema":feed.SCHEMA,"datasets":self.source,
            "customer_delivery_authorized":True,
        }))
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_ENTERPRISE_SOURCE_STATE"):
            self.run_once()

if __name__ == "__main__":
    unittest.main(verbosity=2)
