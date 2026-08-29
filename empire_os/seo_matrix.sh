#!/bin/bash
# seo_matrix — daily EmpireSEO sweep: niche x metro combos via hub.
# Serp discovery (serper) + empire_seo audits of top domains; SEO-weak
# domains (score<=70) auto-fed to crm_leads by /v1/seo/audit.
set -u
HUB=http://127.0.0.1:8081
NICHES="roofing plumbing hvac electrical"
METROS="Nashville TN|Plano TX|Dallas TX"
for niche in $NICHES; do
  IFS='|' read -ra MS <<< "$METROS"
  for metro in "${MS[@]}"; do
    [ -z "$metro" ] && continue
    echo "[seo_matrix] $niche / $metro"
    # 1. discover domains via serp sweep (feeds crm_leads via serper path)
    curl -s -m 90 -X POST "$HUB/v1/serp/sweep" \
      -H 'Content-Type: application/json' \
      -d "{\"niche\":\"$niche\",\"metro\":\"$metro\",\"limit\":10,\"score\":true}" >/dev/null
    # 2. audit top 3 organic domains for this combo (GET web search)
    for q in "best $niche $metro" "$niche company $metro" "affordable $niche near $metro"; do
      DOMS=$(curl -s -m 20 "$HUB/v1/web/search?q=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$q")&num=5" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    rs=d.get("results") or d.get("organic") or d.get("data",{}) or []
    if isinstance(rs,dict): rs=rs.get("organic") or []
    out=[]
    for r in rs:
        u=(r.get("link") or r.get("url") or "")
        host=u.split("/")[2] if "://" in u else ""
        if host and not any(s in host for s in ("youtube.","facebook.","yelp.","reddit.","linkedin.","instagram.","x.com","x.ai","bbb.org","angi.com","thumbtack")):
            out.append(host)
    seen=set(); uniq=[x for x in out if not (x in seen or seen.add(x))]
    print("\n".join(uniq[:3]))
except Exception: pass')
      for dom in $DOMS; do
        curl -s -m 60 -X POST "$HUB/v1/seo/audit" \
          -H 'Content-Type: application/json' \
          -d "{\"url\":\"https://$dom\",\"niche\":\"$niche\",\"metro\":\"$metro\",\"feed_crm\":true}" \
          | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(" ", d.get("domain"), "score", d.get("score"), "fed", d.get("lead_fed"))
except Exception: pass'
      done
    done
  done
done
echo "[seo_matrix] done $(date -Is)"
