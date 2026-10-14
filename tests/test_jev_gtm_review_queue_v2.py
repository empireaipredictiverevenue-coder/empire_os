"""Tenant-scoped batch review and read-only command-line tests."""
import json
from datetime import datetime, timezone
import pytest
from empire_os.jev_gtm_v2 import build_jev_gtm_review_queue
from scripts.review_jev_gtm_candidates_v2 import main

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)

def case(key, *, reply=None, economic=None, tenant="tenant:1", optout=False):
    return {
        "account": {
            "entity_id": "ent:" + key, "tenant_id": tenant,
            "opportunity_key": key, "entity_verified": True,
            "tenant_binding_verified": True, "description": "roofing hiring expansion",
            "target_buyer_pools": ["local_and_smb_buyers"],
            "target_product_codes": ["managed_service"],
            "first_party_people": [{"title": "owner"}],
        },
        "signals": [{
            "signal_id": "s:" + key, "signal_type": "hiring",
            "source_id": "src:" + key, "observed_at": NOW.isoformat(),
            "evidence_refs": ["evidence:" + key], "truth_class": "OBSERVED",
            "entity_id": "ent:" + key, "tenant_id": tenant,
        }],
        "outreach": {"suppression_checked": True, "suppressed": optout},
        "reply": ({
            "source_ref": "email:" + key, "received_at": NOW.isoformat(),
            "entity_id": "ent:" + key, "tenant_id": tenant,
            "thread_linkage_verified": True, "body_text": reply,
        } if reply else None),
        "quant_packet": ({
            "tenant_id": tenant, "opportunity_key": key,
            "actual_revenue": False, "execution_authority": "none",
            "value_available": True, "expected_gross_profit_cents": economic,
        } if economic is not None else None),
    }


def queue(cases):
    return build_jev_gtm_review_queue(tenant_id="tenant:1", cases=cases, as_of=NOW)


def test_reply_first_no_contact_executed():
    row = queue([case("cold"), case("reply", reply="Sounds interesting")])
    assert [v["opportunity_key"] for v in row["items"]] == ["reply", "cold"]
    assert row["outbound_sent"] is False
    assert row["database_write"] is False
    assert row["execution_authority"] == "none"


def test_modelled_profit_tiebreaks_only_same_review_class():
    row = queue([case("small", economic=100), case("big", economic=900)])
    assert [v["opportunity_key"] for v in row["items"]] == ["big", "small"]
    assert row["priority_basis"].endswith("not_probability")


def test_no_mixing_tenants():
    with pytest.raises(ValueError, match="mixed tenant"):
        queue([case("ok"), case("wrong", tenant="tenant:2")])


def test_rejects_duplicate_opportunity():
    with pytest.raises(ValueError, match="duplicate opportunity"):
        queue([case("dup"), case("dup")])


def test_bound_prevents_large_batches():
    with pytest.raises(ValueError, match="limit"):
        build_jev_gtm_review_queue(
            tenant_id="tenant:1", cases=[case("a"), case("b")],
            as_of=NOW, max_candidates=1,
        )


def test_suppressed_contact_sorted_last():
    row = queue([case("hold", optout=True), case("active")])
    assert row["items"][-1]["action"] == "HOLD"


def test_cli_summary_is_readonly(tmp_path, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [case("ok")]}))
    code = main(["--input", str(path), "--tenant-id", "tenant:1",
                 "--as-of", NOW.isoformat()])
    assert code == 0
    row = json.loads(capsys.readouterr().out)
    assert row["item_count"] == 1
    assert row["database_write"] is False
    assert row["outbound_sent"] is False
    assert "items" not in row


def test_cli_refuses_mixed_tenant_without_leaking_raw_details(tmp_path, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [case("bad", tenant="tenant:2")]}))
    code = main(["--input", str(path), "--tenant-id", "tenant:1",
                 "--as-of", NOW.isoformat()])
    row = json.loads(capsys.readouterr().out)
    assert code == 2
    assert row["status"] == "HELD_INVALID_OR_UNTRUSTED_INPUT"
    assert "bad" not in json.dumps(row)


def test_cli_refuses_symlink(tmp_path, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": []}))
    link = tmp_path / "alias.json"
    link.symlink_to(path)
    assert main(["--input", str(link), "--tenant-id", "tenant:1", "--as-of", NOW.isoformat()]) == 2
    assert "HELD" in capsys.readouterr().out
