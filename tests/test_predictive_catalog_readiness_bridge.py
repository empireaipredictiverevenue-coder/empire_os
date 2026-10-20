"""Readiness adapter reconciles source owner blockers without commercial promotion."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

import pytest

from empire_os.commercial_product_catalog import summarize_catalog
from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS
from empire_os.predictive_catalog_readiness_bridge import (
    CUSTODY_STATUS, ProductContractHold, _read_bounded_file,
    _review_catalogue, review_existing_local_catalogue,
)
import scripts.review_predictive_catalog_readiness_20261020 as cli

NOW = datetime(2026, 10, 20, 18, 15, tzinfo=timezone.utc)


def row(code, name, family, price_cents=100_00, *, ready=False):
    truth = {"state": "VERIFIED" if ready else "UNKNOWN"}
    return {
        "product_code": code, "product_name": name, "product_family": family,
        "active": True, "version": "1",
        "catalog_state": "VERIFIED" if ready else "UNKNOWN",
        "version_state": "VERIFIED" if ready else "PENDING",
        "price_basis": {**({"state": "VERIFIED"} if family == "predictive_revenue" else truth), "amount_cents": price_cents, "currency": "USD"},
        "acquisition_cost_basis": truth,
        "fulfilment_cost_basis": truth,
        "margin_policy": truth,
        "binding_terms_ready": ready,
    }


def catalog():
    rows = [
        row(p.product_code, p.name, "predictive_revenue", p.deployment_price_cents)
        for p in PREDICTIVE_REVENUE_PRODUCTS
    ] + [row("competitor_search_gap", "Competitor Search Gap",
              "search_intelligence", ready=True)]
    source = summarize_catalog(rows)
    source["generated_at"] = NOW.isoformat()
    return source


def test_reconcile_tiers_search_ready_and_all_source_blockers():
    c = catalog()
    before = deepcopy(c)
    x = _review_catalogue(c, as_of=NOW)
    assert c == before
    assert x["catalogue_product_count"] == 6
    assert x["catalogue_active_count"] == 6
    assert x["catalogue_terms_ready_count"] == 1
    assert len(x["flagship_deployments"]) == 5
    assert x["family_terms_flag_counts"] == {"search_intelligence": 1}
    assert x["source_original_db_receipt_authenticated"] is False
    assert x["tenant_customer_forecast_verified"] is False
    assert x["execution_authority"] == "none"
    assert all(not p["customer_deployment_verified"] for p in x["flagship_deployments"])
    search = next(p for p in x["products"] if p["product_code"] == "competitor_search_gap")
    assert search["terms_policy_state"].startswith("CATALOGUE_TERMS_FLAG_OBSERVED")
    assert search["buyer_purchasing_authority_verified"] is False
    assert search["first_owner_action"] == "TENANT_EVIDENCE_OWNER_VERIFY_CUSTOMER_AND_CONTRACT"


@pytest.mark.parametrize("mutator", [
    lambda c: c.update(active_count=0),
    lambda c: c.update(blocker_counts={}),
    lambda c: c.update(execution_authority="send"),
    lambda c: c.update(actual_revenue=True),
    lambda c: c["products"][0]["readiness_blockers"].clear(),
    lambda c: c["products"][0].update(binding_terms_ready=True),
    lambda c: c["products"][0]["price_basis"].update(amount_cents=1),
    lambda c: c["products"][0]["price_basis"].update(currency="GBP"),
    lambda c: c["products"].pop(),
    lambda c: c.update(generated_at="not-a-date"),
    lambda c: c.update(generated_at="2026-10-10T00:00:00Z"),
    lambda c: c.update(generated_at="2026-10-20T20:00:00Z"),
])
def test_bad_catalogue_fail_closed(mutator):
    c = catalog()
    mutator(c)
    with pytest.raises(ProductContractHold):
        _review_catalogue(c, as_of=NOW)


def test_empty_or_missing_tier_not_declared_complete():
    c = catalog()
    c["products"].pop(0)
    c = summarize_catalog(c["products"]) | {"generated_at": NOW.isoformat()}
    with pytest.raises(ProductContractHold, match="missing original"):
        _review_catalogue(c, as_of=NOW)


def test_source_custody_tied_to_fd_metadata_and_digest(tmp_path: Path):
    path = tmp_path / "source.json"
    content = json.dumps(catalog()).encode()
    path.write_bytes(content)
    path.chmod(0o600)
    got, fingerprint, mtime = _read_bounded_file(path, owner_uid=os.getuid())
    assert got["product_count"] == 6
    assert len(fingerprint) == 64 and mtime.utcoffset() == timedelta()
    assert CUSTODY_STATUS == "ROOT_OWNED_LOCAL_SNAPSHOT_ONLY_NOT_DB_PROOF"


def test_untrusted_owner_and_symlink_and_group_writable_hold(tmp_path: Path):
    path = tmp_path / "source.json"
    path.write_bytes(json.dumps(catalog()).encode())
    path.chmod(0o600)
    with pytest.raises(ProductContractHold):
        _read_bounded_file(path, owner_uid=-1)
    path.chmod(0o660)
    with pytest.raises(ProductContractHold):
        _read_bounded_file(path, owner_uid=os.getuid())
    path.chmod(0o600)
    shortcut = tmp_path / "shortcut.json"
    shortcut.symlink_to(path)
    with pytest.raises(ProductContractHold):
        _read_bounded_file(shortcut, owner_uid=os.getuid())


def test_nonjson_source_and_truncated_or_oversized_rejected(tmp_path: Path):
    path = tmp_path / "source.json"
    path.write_text("{bad", encoding="utf8")
    path.chmod(0o600)
    with pytest.raises(ProductContractHold):
        _read_bounded_file(path, owner_uid=os.getuid())
    path.write_bytes(b"{" + b"x" * 700_001)
    with pytest.raises(ProductContractHold):
        _read_bounded_file(path, owner_uid=os.getuid())


def test_cli_safe_hold_does_not_expose_user_data(monkeypatch, capsys):
    def fail():
        raise ProductContractHold("secret MUST_NOT_LEAK")
    monkeypatch.setattr(cli, "review_existing_local_catalogue", fail)
    code = cli.main(["--read-only"])
    response = capsys.readouterr().out
    assert code == 2
    assert "MUST_NOT_LEAK" not in response
    report = json.loads(response)
    assert report["source_original_db_receipt_authenticated"] is False
    assert report["execution_authority"] == "none"
    assert report["database_writes"] is False


def test_cli_summary_is_not_raw_86_sku_projection(monkeypatch, capsys):
    monkeypatch.setattr(cli, "review_existing_local_catalogue",
                        lambda: _review_catalogue(catalog(), as_of=NOW))
    assert cli.main(["--read-only"]) == 0
    assert "products" not in json.loads(capsys.readouterr().out)
    assert cli.main(["--read-only", "--all-products"]) == 0
    assert len(json.loads(capsys.readouterr().out)["products"]) == 6
