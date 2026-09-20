from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

from empire_os.hunter.prioritization import rank_enrichment_candidates
from empire_os.qualification_worker_v2 import request_json


def _get(path: str, params: dict[str, str]) -> list[dict[str, Any]]:
    q=urllib.parse.urlencode(params)
    rows=request_json("GET", f"{path}?{q}") or []
    return [r for r in rows if isinstance(r,dict)]


def build_priority_queue(limit: int = 25) -> dict[str, Any]:
    limit=max(1,min(int(limit),100))
    scores=_get("/rest/v1/intelligence_scores",{
        "select":"id,entity_id,score,confidence,features,scored_at",
        "entity_type":"eq.company",
        "score_type":"eq.omega_opportunity",
        "order":"scored_at.desc",
        "limit":str(limit),
    })
    seen=set(); rows=[]
    for score in scores:
        eid=str(score.get("entity_id") or "")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        contacts=_get("/rest/v1/intelligence_contact_points",{
            "select":"id,verification_state,confidence",
            "entity_id":f"eq.{eid}",
            "contact_type":"eq.work_email",
            "limit":"25",
        })
        ready=any(
            str(c.get("verification_state") or "")=="verified"
            and float(c.get("confidence") or 0)>=0.9
            for c in contacts
        )
        features=score.get("features") if isinstance(score.get("features"),dict) else {}
        evidence=float(
            features.get("qualification_evidence_confidence")
            or score.get("confidence") or 0
        )
        rows.append({
            "entity_id":eid,
            "evidence_confidence":evidence,
            "omega_score":score.get("score"),
            "omega_confidence":score.get("confidence"),
            "contact_ready":ready,
            "modeled_expected_gp_cents":None,
            "enrichment_cost_cents":None,
            "evidence_refs":[f"omega_score:{score.get('id')}"],
        })
    ranked=rank_enrichment_candidates(rows)
    return {
        "schema_version":"empire_hunter_priority.v1",
        "mode":"OBSERVE",
        "count":len(ranked),
        "items":[x.as_dict() for x in ranked],
        "outbound_actions":False,
        "payment_actions":False,
        "revenue_actions":False,
    }


def write_priority_snapshot(result: dict[str,Any], path: str|Path="/srv/empire_os/runtime/hunter/priorities.json") -> Path:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    tmp.replace(p)
    return p
