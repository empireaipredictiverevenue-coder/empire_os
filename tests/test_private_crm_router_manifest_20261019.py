"""No public docs needed for authenticated CRM additive release parity."""
from __future__ import annotations

from copy import deepcopy
import subprocess
from pathlib import Path

import pytest

from scripts.verify_private_crm_router_parity_20261019 import (
    BASE, STAGED, NEW_PATH, RouteManifestHeld,
    _root_manifest, compare,
)


def source():
    return _root_manifest(BASE), _root_manifest(STAGED)


def test_exact_existing_27_endpoint_contracts_are_unchanged_and_one_get_added():
    before,after=source()
    result=compare(before,after)
    assert result["prior_routes_verified"] == 27
    assert result["new_routes_verified"] == 28
    assert result["added_route"]==NEW_PATH
    assert result["openapi_endpoint_required"] is False
    assert result["crm_mutation"] is False


@pytest.mark.parametrize("breakage",[
    lambda d: d.pop(),
    lambda d: d.append(deepcopy(d[0])),
    lambda d: d.__setitem__(0,dict(d[0],methods=["POST"])),
    lambda d: d.__setitem__(0,dict(d[0],endpoint_signature="unexpected")),
    lambda d: d.__setitem__(0,dict(d[0],response_class="Untrusted")),
    lambda d: d.__setitem__(0,dict(d[0],include_in_schema=False)),
])
def test_protect_existing_endpoints_from_partial_or_changed_candidate(breakage):
    before,after=source()
    breakage(after)
    with pytest.raises(RouteManifestHeld):
        compare(before,after)


@pytest.mark.parametrize("field,new",[
    ("methods",["POST"]),
    ("name","untrusted_writer"),
    ("include_in_schema",False),
])
def test_new_route_must_be_private_read_get_contract(field,new):
    before,after=source()
    for row in after:
        if row["path"]==NEW_PATH:
            row[field]=new
            break
    with pytest.raises(RouteManifestHeld):
        compare(before,after)


def test_frozen_release_is_exactly_allowlisted():
    with pytest.raises(RouteManifestHeld,match="UNEXPECTED_RELEASE_ROOT"):
        _root_manifest(Path("/srv/empire_os"))


def test_cli_succeeds_without_docs_or_private_credentials():
    r=subprocess.run([
        "/srv/empire_os/.venv/bin/python", "-B", "-m",
        "scripts.verify_private_crm_router_parity_20261019", "--compare-staged"
    ],cwd="/srv/empire_os",capture_output=True,text=True,timeout=25)
    assert r.returncode==0
    assert '"status": "CRM_PRIOR_ROUTER_CONTRACTS_PRESERVED_ONE_GET_ADDED"' in r.stdout


def test_pilot_intentionally_keeps_openapi_disabled():
    service=BASE/"empire_os/revenue_crm_pilot_service.py"
    content=service.read_text()
    assert "docs_url=None, redoc_url=None, openapi_url=None" in content
