"""No live DB: exercise dedicated tenant writer contract and fail-closed HTTP."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_design_store import (
    PostgresCrmJourneyDesignStore, JourneyStorageUnavailable, ROLE, TABLE,
)
from empire_os.revenue_crm_designs import UnsafeJourneyDesign

from tests.test_revenue_crm_designs import TENANT, OTHER, DESIGN, draft

MIGRATION = Path(__file__).resolve().parents[1] / (
    "migrations/empiredb/045_crm_journey_design_versions.sql"
)


class Cursor:
    def __init__(self, db): self.db=db; self.rows=[]
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.db["queries"].append((sql,params))
        if "pg_catalog.pg_has_role(session_user" in sql:
            self.rows = self.db.get("privileges", (True, False, False, False))
        elif sql.startswith("SELECT public.empire_current_tenant_id()"):
            self.rows = (self.db.get("db_tenant", TENANT),)
        elif sql.startswith("SELECT revision,design_sha256 FROM "):
            if "AND revision=%s" in sql:
                rec=self.db["revisions"].get(params[2])
                self.rows=rec
            else:
                self.rows=next((self.db["revisions"][k] for k in sorted(self.db["revisions"],reverse=True)),None)
        elif sql.startswith("INSERT INTO "):
            assert TABLE in sql
            assert params[0] == TENANT
            assert params[1] == DESIGN
            assert params[2] not in self.db["revisions"]
            assert '"execution_authority": "none"' in params[3]
            self.db["revisions"][params[2]]=(params[2],params[4])
            self.rows=(params[2],params[4])
        elif "pg_advisory_xact_lock" in sql:
            assert params == (TENANT, DESIGN)
        else:
            assert sql.startswith("SET "),sql
    def fetchone(self): return self.rows


class Conn:
    def __init__(self, db):self.db=db
    def __enter__(self):return self
    def __exit__(self, *args):return False
    def cursor(self):return Cursor(self.db)


def store(db):
    return PostgresCrmJourneyDesignStore(
        "FAKE_DSN_NO_NETWORK", authenticated_tenant_id=TENANT,
        connect_factory=lambda _dsn: Conn(db),
    )


def test_dedicated_tenant_writer_append_revision_idempotent():
    db={"queries":[],"revisions":{}}
    repo=store(db)
    # A new design ID is generated server-side, never supplied as authority.
    # Simulate server UUID generation using override test of prepare function.
    import empire_os.revenue_crm_design_store as module
    original=module.prepare_design_revision
    def fixed_prepare(value, **kw):
        return original(value, **dict(kw, design_id=DESIGN))
    from unittest.mock import patch
    with patch.object(module,"prepare_design_revision",fixed_prepare):
        created=repo.save(draft())
        assert created.result=="INSERTED" and created.revision==1
        d=draft();d["revision"]=2
        second=repo.save(d, design_id=DESIGN, expected_prior_revision=1)
        assert second.result=="INSERTED" and second.revision==2
        repeated=repo.save(d, design_id=DESIGN, expected_prior_revision=1)
        assert repeated.result=="ALREADY_SAVED_SAME_CONTENT"
        stale=draft();stale["revision"]=2;stale["name"]="Changed human review"
        with pytest.raises(UnsafeJourneyDesign,match="conflict"):
            repo.save(stale, design_id=DESIGN, expected_prior_revision=1)
    assert list(db["revisions"])==[1,2]
    assert any("SET LOCAL ROLE "+ROLE in q[0] for q in db["queries"])
    assert all("UPDATE public.empire_crm_journey" not in q[0] for q in db["queries"])


def test_tenant_binding_and_role_mismatch_stop_before_insert():
    for overrides in (
        {"db_tenant": OTHER},
        {"privileges": (False,False,False,False)},
        {"privileges": (True,True,False,False)},
        {"privileges": (True,False,True,False)},
    ):
        db={"queries":[],"revisions":{},**overrides}
        with pytest.raises(JourneyStorageUnavailable):
            store(db).save(draft())
        assert db["revisions"] == {}


def test_server_writer_cannot_claim_active_workflow_and_is_not_live_in_router():
    app=FastAPI()
    app.include_router(create_revenue_crm_router())
    c=TestClient(app)
    for body in (
        {"design":draft()},
        {"design":dict(draft(),execution_authority="live")},
    ):
        r=c.post("/v1/revenue-crm/journeys/designs/drafts",json=body)
        assert r.status_code == 503
    with pytest.raises(ValueError,match="authenticated CRM tenant resolver"):
        create_revenue_crm_router(
            resolve_authenticated_design_writer=lambda _:store({"queries":[],"revisions":{}})
        )


def test_prepared_migration_is_append_only_tenant_rls_no_login_grants():
    sql=MIGRATION.read_text()
    assert "PREPARED-ONLY" in sql
    assert "empire_crm_journey_design_versions" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "tenant_id=public.empire_current_tenant_id()" in sql
    assert "INSERT" in sql and "GRANT SELECT,INSERT" in sql
    assert "REVOKE ALL" in sql
    for forbidden in ("CREATE LOGIN", "CREATE USER", "GRANT UPDATE", "GRANT DELETE",
                      "TO empiredb_app;", "GRANT EXECUTE ON public.outbound"):
        assert forbidden not in sql
