"""Bounded no-network regression suite for the original brokerage enterprise feed."""
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from empire_os import data_brokerage_enterprise_feed as m

T0 = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
FEMA = "us_disaster_declaration_activity"

def row(ident="5000", event="Fire", stamp="2026-11-18T10:00:00+00:00"):
    r = {k: "" for k in m.HEADERS[FEMA]}
    r.update(disaster_number=ident, declaration_id="FM-" + ident,
             state="CA", fips_county="001", county_designated_area="Alameda",
             declaration_date="2026-11-18", event_type=event,
             source_url="https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
             observed_at=stamp)
    return r

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.state = self.p/"runtime/state.json"
        self.root = self.p/"datasets"
        self.root.mkdir()
        self.source_config = patch.object(
            m, "SOURCES", {FEMA: (12, 1, 5, "FEMA")})
        self.source_config.start()
        self.addCleanup(self.source_config.stop)

    def invoke(self, stamp=T0, rows=None, func=None):
        fn = func or (lambda x: (rows if rows is not None else [row()], "https://source"))
        return m.run_due(self.p, now=stamp, fetchers={FEMA:fn},
                         state_path=self.state,dataset_root=self.root,
                         allow_noncanonical=True)

    def test_first_source_and_safe_contract(self):
        result = self.invoke()
        self.assertEqual(result["status"], "VERIFIED_CHANGED")
        self.assertEqual(result["new"], 1)
        self.assertFalse(result["customer_delivery_authorized"])
        state=json.loads(self.state.read_text())
        self.assertFalse(state["source_redistribution_approved"])
        self.assertFalse(state["commercial_sales_authorized"])
        self.assertEqual(state["datasets"][FEMA]["row_count"],1)
        self.assertEqual(self.root.joinpath(FEMA+".csv").stat().st_mode & 0o777, 0o600)

    def test_same_scheduler_cycle_no_extra_fetch(self):
        self.invoke()
        def forbidden(_):raise AssertionError("source should not be called")
        second=self.invoke(T0+timedelta(minutes=20),func=forbidden)
        self.assertEqual(second["status"],"PROFESSIONAL_FEED_ALL_SOURCES_WITHIN_CADENCE")
        self.assertEqual(second["network_requests"],0)

    def test_changed_fingerprint_ignores_poll_and_source_url(self):
        self.invoke()
        prior = self.root.joinpath(FEMA+".csv").read_bytes()
        unchanged = row(stamp="new poll")
        unchanged["source_url"] = "https://example.org/metadata-change"
        result=self.invoke(T0+timedelta(hours=12),rows=[unchanged])
        self.assertEqual(result["status"], "VERIFIED_UNCHANGED")
        self.assertEqual(self.root.joinpath(FEMA+".csv").read_bytes(),prior)
        self.assertEqual(result["changed"],0)

    def test_json_null_and_csv_empty_equivalent(self):
        self.invoke()
        received = row(stamp="later")
        received["source_last_refresh"] = None
        received["incident_begin_date"] = None
        out = self.invoke(T0+timedelta(hours=12), rows=[received])
        self.assertEqual(out["status"], "VERIFIED_UNCHANGED")
        self.assertEqual(out["changed"], 0)

    def test_actual_change_creates_archive(self):
        self.invoke()
        result=self.invoke(T0+timedelta(hours=12),rows=[row(event="Hurricane")])
        self.assertEqual(result["changed"],1)
        self.assertEqual(result["new"],0)
        self.assertEqual(len(list((self.root/"history").glob("*.csv"))),1)

    def test_failure_retains_last_good_snapshot(self):
        self.invoke()
        original=self.root.joinpath(FEMA+".csv").read_bytes()
        def failed(_):raise TimeoutError("test")
        out=self.invoke(T0+timedelta(hours=12),func=failed)
        self.assertEqual(out["status"],"SOURCE_REFRESH_HELD")
        self.assertEqual(self.root.joinpath(FEMA+".csv").read_bytes(),original)
        self.assertFalse(json.loads(self.state.read_text())["datasets"][FEMA]["quality_pass"])

    def test_failure_retries_after_hour_not_seven_days(self):
        self.invoke()
        calls=[]
        def failed(_):
            calls.append(1)
            raise TimeoutError("transient")
        self.invoke(T0+timedelta(hours=12),func=failed)
        self.assertEqual(len(calls),1)
        skipped=self.invoke(T0+timedelta(hours=12,minutes=30),func=failed)
        self.assertEqual(skipped["network_requests"],0)
        retry=self.invoke(T0+timedelta(hours=13,minutes=1),rows=[row()])
        self.assertEqual(retry["status"],"VERIFIED_UNCHANGED")
        self.assertEqual(retry["changed"],0)

    def test_duplicate_identifier_failclosed(self):
        self.invoke()
        original=self.root.joinpath(FEMA+".csv").read_bytes()
        out=self.invoke(T0+timedelta(hours=12),rows=[row(),row()])
        self.assertEqual(out["status"],"SOURCE_REFRESH_HELD")
        self.assertEqual(self.root.joinpath(FEMA+".csv").read_bytes(),original)

    def test_count_underflow_failclosed(self):
        self.invoke()
        out=self.invoke(T0+timedelta(hours=12),rows=[])
        self.assertEqual(out["status"],"SOURCE_REFRESH_HELD")

    def test_invalid_prior_receipt_failclosed(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text('{"schema":"unexpected"}')
        with self.assertRaisesRegex(ValueError,"EXISTING_PROFESSIONAL_FEED_STATE_INVALID"):
            self.invoke()

    def test_multiple_source_order_and_one_per_cycle(self):
        with patch.object(m,"SOURCES",{"us_disaster_declaration_activity":(12,1,5,"FEMA"),
                        "global_legal_entity_identity_gb":(24,1,5,"GLEIF")}):
            def getter(_):
                return [row()], "https://source"
            first=m.run_due(self.p,now=T0,state_path=self.state,dataset_root=self.root,
                 fetchers={FEMA:getter},allow_noncanonical=True)
            self.assertEqual(first["source"],FEMA)
            # Next source handler can be checked separately: no double request per call.
            self.assertNotIn("global_legal_entity_identity_gb",json.loads(self.state.read_text())["datasets"])

    def test_manual_owner_does_not_fabricate_scheduled_receipt(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"INVOCATION_ID": ""}):
            result = m.record_scheduled_owner_observation(
                Path("/srv/empire_os"), {"status": "VERIFIED_UNCHANGED"},
                {"status": "VIEW_VERIFIED_INTERNAL"}, now=T0)
        self.assertFalse(result["timer_receipt_written"])

    def test_noncanonical_cannot_spoof_systemd_receipt(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"INVOCATION_ID": "0"*32}):
            result = m.record_scheduled_owner_observation(
                self.p, {"status": "VERIFIED_UNCHANGED"},
                {"status": "VIEW_VERIFIED_INTERNAL"}, now=T0)
        self.assertFalse(result["timer_receipt_written"])

    def test_noncanonical_protected_by_default(self):
        self.assertEqual(m.run_due(self.p)["status"],"NONCANONICAL_ROOT_HELD")

if __name__ == "__main__":
    unittest.main(verbosity=2)
