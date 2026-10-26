#!/usr/bin/env python3
"""Guarded four-page, HTML-only internal link addition to CURRENT Empire site.

Only inserts exactly eight existing-source-authorised anchor links inside the
already live Connected Intelligence section of four current industry pages.
Precondition: current production HTML byte-identical to publicly served HTML.
Fail closed and rollback changed files on any source/hash/HTTP regression.
No Next.js overwrite, old assets, gateway restart, database or email writes.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SITE = "https://empire-ai.co.uk"
BASE = Path("/srv/empire_os/apps/empire-public-site/out/industries")
SOURCE = Path("/srv/empire_os/apps/empire-public-site/src/lib/industry-pages.ts")
RELEASE = Path("/home/ubuntu/empire_releases/seo_four_industry_contextual_overlay_20261026_v1")

LINKS = {
 "roofing": (
  ("DFW roofing market guide", "/aeo/roofing/DFW/"),
  ("Denver roofing coverage-gap worksheet", "/research/campaign_3438b6c3b110f941407ce1dd"),
 ),
 "hvac": (
  ("Dallas–Fort Worth HVAC market guide", "/aeo/hvac/DFW/"),
  ("DFW HVAC pilot research worksheet", "/research/campaign_99a64a18052abf58600b64a6"),
  ("Denver HVAC source-validation guide", "/research/campaign_83ccabdbe7356a6f17d77440"),
 ),
 "property": (
  ("New York general-contractor market guide", "/aeo/general_contractor/NYC/"),
  ("NYC contractor evidence-chain checklist", "/research/campaign_7d5e758b1ec56415de7516a6"),
 ),
 "legal-mass-tort": (
  ("Atlanta legal-intelligence research brief", "/research/campaign_948947123543615f2c6eab7f"),
 ),
}
assert sum(len(x) for x in LINKS.values()) == 8

def digest(data: bytes) -> str:
 return hashlib.sha256(data).hexdigest()

def public_read(path: str) -> bytes:
 response = requests.get(SITE + path, timeout=12, headers={"Cache-Control":"no-cache"})
 if response.status_code != 200 or response.url.rstrip("/") != (SITE + path).rstrip("/"):
  raise ValueError("public_https_route_or_redirect_failed:" + path)
 if not response.content or len(response.content) > 2_000_000:
  raise ValueError("public_html_size_out_of_bounds:" + path)
 return response.content

def transform(slug: str, current: bytes) -> tuple[bytes, str]:
 data=current.decode("utf-8")
 marker=">CONNECTED INTELLIGENCE</p>"
 if data.count(marker) != 1:raise ValueError("contextual_section_not_unique:"+slug)
 pos=data.index(marker)
 begin=data.rfind("<section ",0,pos)
 end=data.find("</section>",pos)+len("</section>")
 if begin < 0 or end < len("</section>"):raise ValueError("connected_section_unbounded:"+slug)
 section=data[begin:end]
 marker_div='<div class="mt-9 flex flex-wrap justify-center gap-3">'
 if section.count(marker_div)!=1:raise ValueError("exact_link_row_not_found:"+slug)
 match=re.search(r'<a href="[^"]+" class="([^"]+)">(.+?)</a>',section,re.S)
 if match is None:raise ValueError("existing_anchor_template_missing:"+slug)
 svg=re.search(r'<svg\b.*?</svg>',match.group(2),re.S)
 if svg is None:raise ValueError("existing_icon_missing:"+slug)
 cls=match.group(1)
 suffix="</div></div></section>"
 if not section.endswith(suffix):
  raise ValueError("unexpected_live_panel_closing_markup:"+slug)
 candidate=""
 for label,href in LINKS[slug]:
  if f'href="{href}"' in section:raise ValueError("link_already_published:"+href)
  candidate += '<a href="'+html.escape(href,quote=True)+'" class="'+cls+'">'+html.escape(label)+svg.group(0)+'</a>'
 improved_section=section[:-len(suffix)]+candidate+suffix
 improved=data[:begin]+improved_section+data[end:]
 if improved.replace(candidate,"",1) != data:
  raise ValueError("candidate_modified_unrelated_live_html:"+slug)
 old=BeautifulSoup(data,"html.parser")
 new=BeautifulSoup(improved,"html.parser")
 old_links=[a.get("href") for a in old.select("main a[href]")]
 new_links=[a.get("href") for a in new.select("main a[href]")]
 for _,href in LINKS[slug]:
  if new_links.count(href)!=1:raise ValueError("missing_or_duplicate_exact_anchor:"+href)
 for href in old_links:
  if new_links.count(href)<old_links.count(href):raise ValueError("existing_link_lost:"+slug)
 if len(new_links)-len(old_links)!=len(LINKS[slug]):raise ValueError("link_delta_mismatch:"+slug)
 if (len(old.select("main h1"))!=1 or len(new.select("main h1"))!=1
     or len(old.select('link[rel=canonical]'))!=1):
  raise ValueError("live_seo_structure_not_safe:"+slug)
 if ([(x.name,x.get_text(" ",strip=True)) for x in old.select("main h1,main h2")] !=
      [(x.name,x.get_text(" ",strip=True)) for x in new.select("main h1,main h2")]):
  raise ValueError("original_headings_changed:"+slug)
 if [t.get("href") for t in old.select('link[rel=canonical]')] != [t.get("href") for t in new.select('link[rel=canonical]')]:
  raise ValueError("canonical_changed:"+slug)
 return improved.encode("utf-8"), candidate

def prepare() -> tuple[dict,dict[str,bytes]]:
 if RELEASE.exists():raise ValueError("exclusive_release_receipt_already_exists")
 if not SOURCE.is_file():raise ValueError("site_source_missing")
 source=SOURCE.read_text(encoding="utf-8")
 for slug,links in LINKS.items():
  for _,href in links:
   if source.count('href: "'+href+'"')!=1:
    raise ValueError("nextjs_source_not_converged:"+href)
 before={}
 after={}
 records=[]
 for slug in LINKS:
  dest=BASE/(slug+".html")
  if not dest.is_file() or dest.is_symlink():raise ValueError("missing_normal_current_html:"+slug)
  data=dest.read_bytes()
  if public_read("/industries/"+slug)!=data:
   raise ValueError("public_current_html_not_byte_identical:"+slug)
  new,insert=transform(slug,data)
  records.append({"slug":slug,"pre_sha256":digest(data),"post_sha256":digest(new),
                  "insert_sha256":digest(insert.encode()),"links_added":len(LINKS[slug]),
                  "existing_bytes_preserved_other_than_insertion":True,
                  "before_bytes":len(data),"after_bytes":len(new)})
  before[slug]=data
  after[slug]=new
 checked=set()
 for links in LINKS.values():
  for _,href in links:
   if href not in checked:
    doc=BeautifulSoup(public_read(href),"html.parser")
    if len(doc.select('link[rel=canonical]'))!=1 or len(doc.select("h1"))!=1:
     raise ValueError("target_missing_own_canonical_or_h1:"+href)
    checked.add(href)
 return ({"schema_version":"empire.seo.four_industry_contextual_overlay.v1",
          "mode":"GUARDED_HTML_ONLY_RELEASE","source_sha256":digest(SOURCE.read_bytes()),
          "created_at":datetime.now(timezone.utc).isoformat(),
          "pages":records,"destinations_http_200_self_canonical":len(checked),
          "links_added":sum(len(x) for x in LINKS.values()),
          "source_owners_not_rebuilt":True,"js_assets_changed":False,
          "other_routes_changed":False,"db_writes":False,
          "outbound_sent":False,"payments_changed":False},after)

def install(packet:dict, after:dict[str,bytes]) -> None:
 RELEASE.mkdir(mode=0o700,parents=False,exist_ok=False)
 backup=RELEASE/"html_before"
 backup.mkdir(mode=0o700)
 temp=RELEASE/"html_candidate"
 temp.mkdir(mode=0o700)
 for row in packet["pages"]:
  slug=row["slug"]
  b=BASE/(slug+".html")
  raw=b.read_bytes()
  if digest(raw)!=row["pre_sha256"]:raise ValueError("changed_after_preflight:"+slug)
  (backup/(slug+".html")).write_bytes(raw)
  (temp/(slug+".html")).write_bytes(after[slug])
 (RELEASE/"preflight.json").write_text(json.dumps(packet,sort_keys=True,indent=2)+"\n")
 applied=[]
 try:
  for row in packet["pages"]:
   slug=row["slug"]
   dest=BASE/(slug+".html")
   if digest(dest.read_bytes())!=row["pre_sha256"]:
    raise ValueError("concurrent_writer_changed_live_html:"+slug)
   staged=dest.with_name(dest.name+".seo_overlay_candidate")
   if staged.exists():raise ValueError("candidate_file_collision:"+slug)
   shutil.copy2(temp/(slug+".html"),staged)
   os.replace(staged,dest)
   applied.append(row)
  # Live readback (not merely filesystem) all four pages: exact content digest.
  for row in packet["pages"]:
   slug=row["slug"]
   data=public_read("/industries/"+slug)
   if digest(data)!=row["post_sha256"]:
    raise ValueError("public_gateway_did_not_serve_expected_html:"+slug)
   rendered=BeautifulSoup(data,"html.parser")
   for _,href in LINKS[slug]:
    if len(rendered.select('a[href="'+href+'"]'))!=1:
     raise ValueError("public_contextual_link_missing:"+href)
  packet["status"]="FOUR_LIVE_PAGES_VERIFIED"
  packet["published_at"]=datetime.now(timezone.utc).isoformat()
  (RELEASE/"release_receipt.json").write_text(json.dumps(packet,sort_keys=True,indent=2)+"\n")
  print(json.dumps({"status":packet["status"],"pages":len(packet["pages"]),
                    "links":packet["links_added"],
                    "receipt":str(RELEASE/"release_receipt.json")},sort_keys=True))
 except Exception:
  restored=[]
  for row in reversed(applied):
   slug=row["slug"]
   dest=BASE/(slug+".html")
   if digest(dest.read_bytes())!=row["post_sha256"]:
    continue
   restored_candidate=dest.with_name(dest.name+".seo_overlay_restore")
   shutil.copy2(backup/(slug+".html"),restored_candidate)
   os.replace(restored_candidate,dest)
   restored.append(slug)
  (RELEASE/"release_failed_restored.json").write_text(json.dumps({"attempted":len(applied),
    "restored":restored,"expected_restored":len(applied)},sort_keys=True)+"\n")
  raise

def main():
 parser=argparse.ArgumentParser()
 modes=parser.add_mutually_exclusive_group(required=True)
 modes.add_argument("--dry-run",action="store_true")
 modes.add_argument("--apply",action="store_true")
 parser.add_argument("--approved-founder-contextual-links-only",action="store_true")
 args=parser.parse_args()
 if args.apply and not args.approved_founder_contextual_links_only:
  parser.error("explicit_founder_four_page_scope_required")
 packet,after=prepare()
 if args.dry_run:
  print(json.dumps({"status":"PREFLIGHT_ONLY","pages":len(packet["pages"]),
                    "links":packet["links_added"],
                    "destinations_http_200":packet["destinations_http_200_self_canonical"],
                    "expected_after_hashes":[(x["slug"],x["post_sha256"]) for x in packet["pages"]]},
                   sort_keys=True))
 else:
  install(packet,after)

if __name__=="__main__":
 main()
