#!/usr/bin/env python3
"""One-hit bounded owned-site crawlability inspection without changing live SEO.

Only HTTPS empire-ai.co.uk pages from the first-party sitemap and six fixed
buyer/legal draft gates. No redirects, no search engines, no customer data,
no indexing, no publishing, no task timers or new collection runtime.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
import xml.etree.ElementTree as ET

from empire_os.search_intelligence.owned_indexability_review import (
    _owned_url, analyse_owned_indexability,
)

ROOT = Path("/var/tmp").resolve()
ORIGIN="https://empire-ai.co.uk"
UA="Mozilla/5.0 (compatible; EmpireSEOOneHitReadOnly/1.0)"
_GATES=(
    "/roofing", "/roofing/replacement-vs-repair",
    "/roofing/installation-checklist", "/research/agent-governance",
    "/privacy", "/terms",
)


class _Headings(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical=[]
        self.robots=[]
        self.h1=0
        self.title=""
        self._title=False

    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=="link" and str(data.get("rel") or "").lower()=="canonical":
            self.canonical.append(data.get("href"))
        if tag=="meta" and str(data.get("name") or "").lower()=="robots":
            self.robots.append(data.get("content"))
        if tag=="h1":self.h1+=1
        if tag=="title":self._title=True

    def handle_endtag(self,tag):
        if tag=="title":self._title=False

    def handle_data(self,content):
        if self._title:self.title+=content


def _get(url: str, *,
         runner: Callable[..., subprocess.CompletedProcess]=subprocess.run) -> dict[str,Any]:
    _owned_url(url)
    args=[
        "curl","-sS","--max-time","6","--max-redirs","0",
        "--compressed","-A",UA,"-D","-",url,
    ]
    call=runner(args,capture_output=True,timeout=9,check=False)
    if call.returncode != 0 or len(call.stdout)>260_000:
        return {"url":url,"http":None,"status":"FETCH_UNAVAILABLE"}
    try:
        split=re.split(rb"\r?\n\r?\n",call.stdout,maxsplit=1)
        if len(split)!=2:raise ValueError("response_missing_headers")
        headers,body=split
        rawstatus=re.search(rb"HTTP/\S+\s+(\d{3})",headers)
        if not rawstatus:raise ValueError("response_missing_status")
        status=int(rawstatus.group(1))
        response={
            "url":url,"http":status,
            "html_robots":[],"xrobots":[],"canonical":[],
            "h1_count":0,"title":"",
            "body":body,
        }
        if status==200:
            if b"<html" in body[:30_000].lower():
                parser=_Headings()
                parser.feed(body.decode("utf-8",errors="replace"))
                response.update({
                    "html_robots":parser.robots,
                    "canonical":parser.canonical,
                    "h1_count":parser.h1,
                    "title":parser.title[:160],
                })
            if any(x is None for x in response["html_robots"]+response["canonical"]):
                return {"url":url,"http":None,"status":"MALFORMED_METADATA"}
        response["xrobots"]=[x.decode("utf-8",errors="replace").strip() for x in
                             re.findall(rb"(?im)^x-robots-tag:\s*([^\r\n]+)",headers)]
        return response
    except (ValueError,UnicodeDecodeError):
        return {"url":url,"http":None,"status":"MALFORMED_HTTP_SOURCE"}


def run(*, output: Path, get: Callable[..., dict[str,Any]]=_get,
        allowed_root: Path=ROOT,
        clock: Callable[[],datetime]=lambda: datetime.now(timezone.utc)) -> dict:
    if output.is_symlink():
        raise ValueError("review_output_symlink_denied")
    dest=output.resolve()
    if dest.exists() or not dest.is_relative_to(allowed_root.resolve()):
        raise ValueError("new_private_review_receipt_required")
    robots=get(ORIGIN+"/robots.txt")
    site=get(ORIGIN+"/sitemap.xml")
    if robots.get("http")!=200 or site.get("http")!=200:
        raise ValueError("cannot_claim_indexability_when_site_evidence_unavailable")
    xml=site.get("body")
    txt=robots.get("body")
    if not isinstance(xml,bytes) or len(xml)>120_000 or not isinstance(txt,bytes) or len(txt)>32_000:
        raise ValueError("unbounded_owned_site_evidence")
    try:
        tree=ET.fromstring(xml)
    except ET.ParseError:
        raise ValueError("untrusted_ownership_sitemap") from None
    urls=[x.text for x in tree.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    if not 1<=len(urls)<=50:
        raise ValueError("unbounded_sitemap_crawl")
    for u in urls:_owned_url(u)
    if len(set(urls))!=len(urls):
        raise ValueError("duplicate_sitemap_url")
    pages=[]
    for u in urls:
        packet=get(u)
        pages.append({k:v for k,v in packet.items() if k!="body"})
    gates=[]
    for path in _GATES:
        packet=get(ORIGIN+path)
        gates.append({
            "path":path,
            "http":packet.get("http"),
            "html_robots":packet.get("html_robots") or [],
            "xrobots":packet.get("xrobots") or [],
            "canonical":packet.get("canonical") or [],
            "title":str(packet.get("title") or "")[:160],
            "h1_count":packet.get("h1_count"),
        })
    stamp=clock()
    if stamp.tzinfo is None:
        raise ValueError("aware_observation_time_required")
    report=analyse_owned_indexability(
        sitemap=xml,robots=txt,pages=pages,
        gated_pages=gates,observed_at=stamp.isoformat(),
    )
    # Keep only evidence summaries, not source body, cookies, or content.
    result={
        "schema_version":"empire.search.owned_indexability_one_hit_probe.v1",
        "mode":"OBSERVE",
        "review":report,
        "source_calls":2+len(pages)+len(gates),
        "site_content_not_persisted":True,
        "outbound_messages_sent":0,
        "website_changed":False,
        "production_db_changed":False,
        "release_receipt_generated":False,
    }
    dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(result,f,indent=2,sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return {
        "status":"OWNED_INDEXABILITY_AUDIT_RECORDED",
        "sitemap_urls":report["sitemap_url_count"],
        "indexability_signal_pages":report["sitemap_indexability_signal_count"],
        "technical_issues":report["needs_technical_review_count"],
        "gated_pages_verified":len(report["expected_gated"]),
        "google_indexed_pages_verified":False,
        "buyers_call_routing_changed":False,
        "private_receipt":str(dest),
    }


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--output",required=True)
    args=cli.parse_args()
    print(json.dumps(run(output=Path(args.output)),sort_keys=True))
