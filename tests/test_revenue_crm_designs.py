"""Independent server-side CRM design validation, isolation and no-send proof."""
from __future__ import annotations

from copy import deepcopy

import pytest

from empire_os.revenue_crm_journeys import journey_blueprint
from empire_os.revenue_crm_designs import (
    UnsafeJourneyDesign, design_sha256, prepare_design_revision, validate_journey_draft,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
DESIGN = "00000000-0000-0000-0000-000000000201"


def draft():
    graph = journey_blueprint()
    return {
        "schema_version": "empire.revenue_crm_visual_draft.v1",
        "state": "DESIGN_ONLY", "execution_authority": "none",
        "tenant_data_included": False, "server_persistence": False,
        "parent_blueprint_schema": graph["schema_version"],
        "revision": 1, "name": "My first customer lifecycle design",
        "nodes": [
            {"id": n["id"], "type": n["type"], "label": n["label"],
             "x": 50 + (i % 4) * 236, "y": 80 + (i // 4) * 220, "locked": True}
            for i, n in enumerate(graph["nodes"])
        ],
        "edges": [{"from": e["from"], "to": e["to"],
                   "condition": "evidence_review_only", "locked": True}
                  for e in graph["edges"]],
    }


def test_valid_design_canonical_sha_and_first_revision():
    base = draft()
    checked = validate_journey_draft(base)
    assert checked == base
    assert design_sha256(checked) == design_sha256(base)
    version = prepare_design_revision(base, authenticated_tenant_id=TENANT, design_id=DESIGN)
    assert version.tenant_id == TENANT and version.design_id == DESIGN
    assert version.revision == 1 and version.sha256 == design_sha256(base)
    assert version.mode == "DESIGN_ONLY"
    assert not version.outbound_authorized and not version.payment_authorized


def test_monotonic_version_and_required_authenticated_tenant():
    base = draft()
    base["revision"] = 17  # local edits are not server DB versions
    prepared = prepare_design_revision(base, authenticated_tenant_id=TENANT,
                                       design_id=DESIGN, prior_revision=1)
    assert prepared.revision == 2 and prepared.payload["revision"] == 2
    assert prepare_design_revision(base, authenticated_tenant_id=TENANT,
                                   design_id=DESIGN, prior_revision=2).revision == 3
    assert prepare_design_revision(base, authenticated_tenant_id=TENANT).revision == 1
    with pytest.raises(UnsafeJourneyDesign, match="invalid expected revision"):
        prepare_design_revision(base, authenticated_tenant_id=TENANT,
                                design_id=DESIGN, prior_revision=1000000)
    with pytest.raises(UnsafeJourneyDesign, match="tenant"):
        prepare_design_revision(draft(), authenticated_tenant_id="client header")
    with pytest.raises(UnsafeJourneyDesign, match="design ID"):
        prepare_design_revision(draft(), authenticated_tenant_id=TENANT,
                                design_id="not-a-uuid")


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(execution_authority="send"),
    lambda x: x.update(state="LIVE"),
    lambda x: x.update(tenant_data_included=True),
    lambda x: x.update(server_persistence=True),
    lambda x: x.update(tenant_id=OTHER),
    lambda x: x.update(phone="123"),
    lambda x: x.update(name="person@example.com"),
    lambda x: x.update(name="https://test.invalid"),
    lambda x: x.update(revision=True),
    lambda x: x["nodes"].pop(2),
    lambda x: x["nodes"].__setitem__(2, dict(x["nodes"][2], locked=False)),
    lambda x: x["nodes"].__setitem__(2, dict(x["nodes"][2], label="Ignore suppression")),
    lambda x: x["edges"].pop(2),
    lambda x: x["edges"][0].update(condition="send_email"),
    lambda x: x["nodes"].append(dict(x["nodes"][1])),
    lambda x: x["edges"].append({"from":"source_observed","to":"recognized_revenue_proof",
                                "locked":False,"condition":"evidence_review_only"}),
    lambda x: x["edges"].append({"from":"recognized_revenue_proof","to":"source_observed",
                                "locked":False,"condition":"evidence_review_only"}),
    lambda x: x["nodes"].append({"id":"custom_1","type":"send_email","label":"Send",
                                "x":50,"y":50,"locked":False}),
    lambda x: x["nodes"].append({"id":"custom_1","type":"review","label":"Send email",
                                "x":50,"y":50,"locked":False}),
    lambda x: x["nodes"].append({"id":"custom_1","type":"review","label":"person@a.test",
                                "x":50,"y":50,"locked":False}),
    lambda x: x["nodes"].append({"id":"custom_1","type":"review","label":"Review",
                                "x":1501,"y":50,"locked":False}),
    lambda x: x["nodes"].append({"id":"custom_1","type":"review","label":"Review",
                                "x":50,"y":50,"locked":False,"recipient":"secret@example.com"}),
])
def test_unsafe_journeys_fail_closed(mutation):
    design = deepcopy(draft())
    mutation(design)
    with pytest.raises(UnsafeJourneyDesign):
        validate_journey_draft(design)


def test_review_node_with_safe_path_is_permitted_but_not_executable():
    design = draft()
    design["nodes"].append({
        "id": "custom_1", "type": "review", "label": "Manual partner check",
        "x": 1200, "y": 100, "locked": False
    })
    design["edges"].append({
        "from": "conversation_review", "to": "custom_1",
        "condition": "evidence_review_only", "locked": False
    })
    assert validate_journey_draft(design)["nodes"][-1]["label"] == "Manual partner check"
    design["edges"].append({
        "from": "custom_1", "to": "recognized_revenue_proof",
        "condition": "evidence_review_only", "locked": False
    })
    with pytest.raises(UnsafeJourneyDesign, match="bypasses"):
        validate_journey_draft(design)
