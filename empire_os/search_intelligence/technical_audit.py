"""Unified observed-evidence technical SEO audit intelligence."""
from __future__ import annotations
from collections import Counter
from typing import Any, Iterable, Mapping

SEVERITY_WEIGHT={"critical":100,"high":40,"medium":15,"low":5,"info":0}
CATEGORY_BY_PREFIX={
 "crawl_":"crawlability","site_canonical":"canonicalization","page_canonical":"canonicalization",
 "duplicate_":"duplication","site_title":"metadata","page_title":"metadata",
 "meta_description":"metadata","structured_data":"structured_data",
 "lighthouse_":"performance","indexation_":"indexation","robots_":"crawlability","sitemap_":"discovery",
}

def _category(code:str)->str:
    return next((v for k,v in CATEGORY_BY_PREFIX.items() if code.startswith(k)),"technical")

def build_technical_audit(*, crawl_audit:Mapping[str,Any]|None=None,
                          lighthouse:Mapping[str,Any]|None=None,
                          extra_findings:Iterable[Mapping[str,Any]]=())->dict[str,Any]:
    findings:list[dict[str,Any]]=[]
    if crawl_audit:
        for raw in crawl_audit.get("findings",[]) or []:
            if not isinstance(raw,Mapping): continue
            row=dict(raw); row["category"]=_category(str(row.get("code") or ""))
            row["source"]="empire_web_intelligence_crawler"; findings.append(row)
    if lighthouse:
        for raw in lighthouse.get("opportunities",[]) or []:
            if not isinstance(raw,Mapping): continue
            code=str(raw.get("code") or raw.get("id") or "lighthouse_opportunity")
            findings.append({"code":code,"severity":str(raw.get("severity") or "medium"),
              "scope":"page","message":str(raw.get("message") or raw.get("title") or code),
              "url":raw.get("url"),"evidence":tuple(raw.get("evidence") or ()),
              "category":"performance","source":"lighthouse_observation"})
    for raw in extra_findings:
        if not isinstance(raw,Mapping): continue
        row=dict(raw); row.setdefault("category",_category(str(row.get("code") or "")))
        row.setdefault("source","observed_search_evidence"); findings.append(row)

    dedup:dict[tuple[str,str,str],dict[str,Any]]={}
    for row in findings:
        key=(str(row.get("code") or ""),str(row.get("url") or ""),str(row.get("source") or ""))
        dedup[key]=row
    rows=list(dedup.values())
    rows.sort(key=lambda r:(-SEVERITY_WEIGHT.get(str(r.get("severity")),0),str(r.get("category")),str(r.get("code")),str(r.get("url") or "")))
    counts=Counter(str(r.get("severity") or "unknown") for r in rows)
    categories=Counter(str(r.get("category") or "technical") for r in rows)
    weighted=sum(SEVERITY_WEIGHT.get(str(r.get("severity")),0) for r in rows)
    return {
      "schema_version":"empire.search.technical-audit.v2","mode":"OBSERVE","execution_allowed":False,
      "available": bool(crawl_audit or lighthouse or rows),"finding_count":len(rows),
      "severity_counts":dict(sorted(counts.items())),"category_counts":dict(sorted(categories.items())),
      "priority_burden":weighted,"findings":rows,
      "remediation_queue":[{"priority":i+1,"code":r.get("code"),"url":r.get("url"),
        "severity":r.get("severity"),"category":r.get("category"),"source":r.get("source")}
        for i,r in enumerate(rows) if r.get("severity")!="info"],
      "synthetic_metrics":0,
      "limitations":["observed_evidence_only","priority_burden_is_triage_weight_not_search_ranking_score",
                     "no_traffic_rank_revenue_or_outcome_inference"],
    }
