"""V16: Gmail draft history in the original founder commercial qualification."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import os
import stat

from empire_os.heat_pump_commercial_review import (
    read_prepared_draft_receipts, review, DRAFT_RECEIPTS,
)

ROOT=Path('/srv/empire_os')

def test_three_actual_workspace_drafts_join_original_qualified_targets():
    now=datetime.now(timezone.utc)
    receipts=read_prepared_draft_receipts(ROOT,now=now)
    assert set(receipts)=={
        "goodenergy.co.uk","altoenergy.co.uk","appianheatpumps.com"
    }
    assert all(x["email_preparation_state"]=="WORKSPACE_DRAFT_CREATED_NOT_SENT"
               and x["email_sent_verified"] is False
               and x["new_outreach_authorized"] is False
               for x in receipts.values())
    report=review(ROOT,now=now)
    assert report["historical_gmail_draft_preparations"]==3
    assert report["verified_payable_buyers"]==0
    assert report["outbound_sent"] is False
    rows={x["domain"]:x for x in report["research_inventory"]}
    for domain in receipts:
        assert rows[domain]["workspace_draft_preparation"]["draft_id"]==receipts[domain]["draft_id"]
        assert rows[domain]["outbound_authorized"] is False


def test_draft_history_stale_or_invalid_is_ignored(tmp_path):
    p=tmp_path/DRAFT_RECEIPTS
    p.parent.mkdir(parents=True)
    valid=json.loads((ROOT/DRAFT_RECEIPTS).read_text())
    now=datetime.now(timezone.utc)
    valid["observed_at"]=(now-timedelta(days=12)).isoformat()
    p.write_text(json.dumps(valid))
    p.chmod(0o600)
    assert read_prepared_draft_receipts(tmp_path,now=now)=={}
    valid["observed_at"]=now.isoformat()
    valid["drafts"][0]["send_authorized"]=True
    p.write_text(json.dumps(valid))
    assert read_prepared_draft_receipts(tmp_path,now=now)=={}
    valid["drafts"][0]["send_authorized"]=False
    p.write_text(json.dumps(valid))
    p.chmod(0o644)
    assert read_prepared_draft_receipts(tmp_path,now=now)=={}
    p.unlink()
    p.symlink_to(ROOT/DRAFT_RECEIPTS)
    assert read_prepared_draft_receipts(tmp_path,now=now)=={}
