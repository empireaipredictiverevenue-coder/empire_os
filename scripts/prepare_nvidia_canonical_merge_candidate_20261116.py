"""Prepare the missing canonical term for NVIDIA's *existing* isolated catalog.

Source is the read-only authenticated NVIDIA model export; all live UUIDs are
preserved so import in merge mode can match records rather than duplicate.
Does not perform an import or modify the current NVIDIA app.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml

from empire_os.nvidia_ontology_shadow import SOURCE_TABLES, TABLE_DESCRIPTIONS

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BACKUP = ROOT / "nvidia-model-before-canonical-descriptions-20261116.yaml"
OUT = ROOT / "nvidia-model-with-canonical-ontology-nodes-20261116.yaml"
VENDOR_SCHEMAS = (ROOT / "vendor/auto_ontology/server/model_interchange/schemas.py")
TERM_ID = "empire-canonical-ontology-nodes-v1"


def build():
    if OUT.exists():
        raise RuntimeError("candidate already exists; no overwrite")
    if BACKUP.stat().st_mode & 0o077:
        raise RuntimeError("original export permissions not private")
    model = yaml.safe_load(BACKUP.read_text())
    databases = model["data_layer"]["databases"]
    if len(databases) != 1:
        raise RuntimeError("unexpected number of databases")
    schemas = databases[0].get("schemas", [])
    if len(schemas) != 1 or schemas[0].get("database_name") != "empire_graph":
        raise RuntimeError("unexpected source schema")
    tables = {t["name"]:t for t in schemas[0]["tables"]}
    if set(tables) != set(SOURCE_TABLES):
        raise RuntimeError("non-synthetic tables present")
    terms = model["semantic_layer"]["terms"]
    found_names = {term["name"] for term in terms}
    expected = {name.replace("_"," ").title() for name in SOURCE_TABLES}
    missing = expected - found_names
    if missing != {"Ontology Nodes"}:
        raise RuntimeError(f"unexpected semantic snapshot: missing={missing}")
    if any(term.get("id") == TERM_ID for term in terms):
        raise RuntimeError("new term ID already present")
    table = tables["ontology_nodes"]
    terms.append({
        "id": TERM_ID,
        "name": "Ontology Nodes",
        "description": TABLE_DESCRIPTIONS["ontology_nodes"],
        "represents": [table["id"]],
        "columns_attributes": [
            {
                "id": "empire-canonical-nodes-attribute-" + col["name"],
                "name": col["name"].replace("_"," ").title(),
                "description": (
                    TABLE_DESCRIPTIONS["ontology_nodes"]
                    if col["name"] == "verification_status"
                    else ""
                ),
                "column_id": col["id"],
            } for col in table["columns"]
        ],
    })
    spec=importlib.util.spec_from_file_location("nvidia_model_schemas_for_merge",VENDOR_SCHEMAS)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned NVIDIA schema not loadable")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    validated=module.AutoOntologyModelDocument.model_validate(model)
    assert len(validated.semantic_layer.terms) == 4
    blob=yaml.safe_dump(model,sort_keys=False,allow_unicode=True)
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as out:
        out.write(blob)
    print(json.dumps({
        "status":"NVIDIA_CANONICAL_MERGE_CANDIDATE_VALIDATED_NOT_APPLIED",
        "vendor_document_valid":True,
        "source_tables":len(tables),
        "existing_terms_preserved":3,
        "new_terms_planned":1,
        "new_term_name":"Ontology Nodes",
        "mode":"nonreplace",
        "private_candidate_path":str(OUT),
        "database_modified":False,
    },indent=2))
if __name__=="__main__":
    build()
