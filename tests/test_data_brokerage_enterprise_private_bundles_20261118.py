"""No-network private bundle, provenance, identity and fail-closed tests."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from empire_os import data_brokerage_enterprise_feed as feed
from empire_os import data_brokerage_enterprise_packaging as pack
from empire_os import data_brokerage_enterprise_private_bundles as bundle

NOW = datetime(2026,11,18,12,30,tzinfo=timezone.utc)
VIEW = "us_disaster_territory_activity_sample"
SOURCE = "us_disaster_declaration_activity"

def hash_bytes(b):
    return hashlib.sha256(b).hexdigest()

class PrivateBundleTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp=Path(t.name)
        self.data=self.tmp/"data"
        self.data.mkdir()
        self.source_json=self.tmp/"source_receipt.json"
        self.view_json=self.tmp/"views_receipt.json"
        self.bundle_json=self.tmp/"bundle_receipt.json"
        self.cfg=patch.object(bundle,"VIEWS",{VIEW:pack.VIEWS[VIEW]})
        self.cfg.start()
        self.addCleanup(self.cfg.stop)
        source_row={k:"" for k in feed.HEADERS[SOURCE]}
        source_row.update(disaster_number="912",state="TX",fips_state="48",
             fips_county="001",county_designated_area="Anderson",
             declaration_date="2026-11-01",event_type="Fire")
        source_data=feed._csv_bytes(SOURCE,[source_row])
        (self.data/(SOURCE+".csv")).write_bytes(source_data)
        output=pack._fema([source_row])
        view_data=pack._encode(pack.VIEWS[VIEW]["columns"],output)
        (self.data/(VIEW+".csv")).write_bytes(view_data)
        self.source={
            "schema":feed.SCHEMA,"customer_delivery_authorized":False,
            "datasets":{SOURCE:{"publisher":"FEMA","source_status":"VERIFIED_UNCHANGED",
             "quality_pass":True,"source_snapshot_sha256":hash_bytes(source_data),
             "last_success_at":NOW.isoformat()}}
        }
        self.view={
            "schema":pack.SCHEMA,"customer_delivery_authorized":False,
            "views":{VIEW:{"status":"VIEW_VERIFIED_INTERNAL",
             "sales_authorized":False,"customer_delivery_authorized":False,
             "source_sha256":hash_bytes(source_data),
             "view_sha256":hash_bytes(view_data),"row_count":1}}
        }
        self.save()

    def save(self):
        self.source_json.write_text(json.dumps(self.source))
        self.view_json.write_text(json.dumps(self.view))

    def call(self):
        return bundle.run_due(self.tmp,now=NOW,allow_noncanonical=True,
             data_root=self.data,source_state=self.source_json,
             view_state=self.view_json,bundle_state=self.bundle_json)

    def test_package_provenance_and_no_customer_rights(self):
        res=self.call()
        self.assertEqual(res["status"],"PRIVATE_RESEARCH_BUNDLE_VERIFIED")
        self.assertEqual(res["bundle_rows"],1)
        self.assertFalse(res["customer_downloads_enabled"])
        path=self.data/"internal_bundles/EAI-STORM_private_research.zip"
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(sorted(z.namelist()),
                 ["README.md","data.csv","field_dictionary.json","manifest.json",
                  "quality_report.json"])
            dic=json.loads(z.read("field_dictionary.json"))
            self.assertTrue(all(c.get("description") for c in dic["columns"]))
            report=json.loads(z.read("quality_report.json"))
            self.assertFalse(report["qualified_buyers_verified"])
            self.assertTrue(report["view_checksum_verified"])
            manifest=json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["view_sha256"],self.view["views"][VIEW]["view_sha256"])
            self.assertEqual(manifest["source_sha256"],
                             self.source["datasets"][SOURCE]["source_snapshot_sha256"])
            self.assertFalse(manifest["customer_delivery_authorized"])
            self.assertFalse(manifest["raw_resale_approved"])
            self.assertFalse(manifest["paid_order_verified"])
            self.assertFalse(manifest["founder_release_approved"])
        receipt=json.loads(self.bundle_json.read_text())
        self.assertFalse(receipt["customer_delivery_authorized"])
        self.assertFalse(receipt["automated_sales"])
        self.assertEqual(receipt["bundles"][VIEW]["archive_sha256"],hash_bytes(path.read_bytes()))

    def test_unchanged_does_not_rewrite(self):
        self.call()
        previous=self.bundle_json.read_bytes()
        next=self.call()
        self.assertEqual(next["bundles_built"],0)
        self.assertEqual(self.bundle_json.read_bytes(),previous)

    def test_source_digest_tamper_fail_closed(self):
        self.source["datasets"][SOURCE]["source_snapshot_sha256"]="0"*64
        self.save()
        r=self.call()
        self.assertEqual(r["bundles_built"],0)
        self.assertFalse((self.data/"internal_bundles/EAI-STORM_private_research.zip").exists())

    def test_source_failure_marks_previous_bundle_held(self):
        self.call()
        self.source["datasets"][SOURCE]["source_status"]="SOURCE_REFRESH_HELD"
        self.source["datasets"][SOURCE]["quality_pass"]=False
        self.save()
        out=self.call()
        self.assertEqual(out["bundles_built"],0)
        self.assertEqual(out["bundles_current"],0)
        r=json.loads(self.bundle_json.read_text())
        self.assertEqual(r["bundles"][VIEW]["status"],"PRIVATE_RESEARCH_BUNDLE_SOURCE_HELD")
        self.assertFalse(r["bundles"][VIEW]["customer_delivery_authorized"])
        self.source["datasets"][SOURCE]["source_status"]="VERIFIED_UNCHANGED"
        self.source["datasets"][SOURCE]["quality_pass"]=True
        self.save()
        restored=self.call()
        self.assertEqual(restored["status"],"PRIVATE_RESEARCH_BUNDLE_VERIFIED")

    def test_archive_tamper_rebuild(self):
        self.call()
        path=self.data/"internal_bundles/EAI-STORM_private_research.zip"
        path.write_bytes(b"tampered")
        r=self.call()
        self.assertEqual(r["status"],"PRIVATE_RESEARCH_BUNDLE_VERIFIED")
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip())

    def test_customer_authority_rejected(self):
        self.source["customer_delivery_authorized"]=True
        self.save()
        with self.assertRaisesRegex(ValueError,"CUSTOMER_DELIVERY_AUTHORITY"):
            self.call()

    def test_noncanonical_root_has_no_side_effect(self):
        r=bundle.run_due(self.tmp)
        self.assertEqual(r["status"],"NONCANONICAL_ROOT_HELD")
        self.assertFalse(self.bundle_json.exists())

if __name__ == "__main__":
    unittest.main(verbosity=2)
