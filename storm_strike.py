#!/usr/bin/env python3
"""
Empire OS — Storm Strike (Empire-USA-Strike angle).
Pulls live NWS severe-weather alerts, extracts affected metros, and fires
restoration + roofing outreach to contractors in those zones via empire-leads.
Runs on a tight cadence (every 2h) so we're first after a storm hits.
"""
import sys, os, json, time, argparse
sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire-leads")

COPY_RESTORE = "/root/feedback/campaigns/vertical_feed_restoration_copy.json"
COPY_ROOF = "/root/feedback/campaigns/vertical_feed_roofing_copy.json"

def get_storm_metros(state="US", limit=8):
    """Return list of {area, state} from live NWS alerts."""
    from empire_leads.engine import discover
    try:
        r = discover("storm", state=state, sources=["nws"], limit=limit)
        leads = r.leads if hasattr(r, "leads") else []
    except Exception as e:
        return [{"error": str(e)}]
    metros = []
    for l in leads:
        st = getattr(l, "state", "") or ""
        # NWS alert areas live in 'address' as 'Comal, TX; Kendall, TX'
        addr = getattr(l, "address", "") or ""
        for chunk in addr.split(";"):
            chunk = chunk.strip()
            if "," in chunk:
                city, s = chunk.rsplit(",", 1)
                metros.append({"area": city.strip(), "state": s.strip() or st})
        # fallback: parse name if address empty
        if not metros:
            nm = getattr(l, "name", "")
            for chunk in nm.split(";"):
                chunk = chunk.strip()
                if "," in chunk:
                    city, s = chunk.rsplit(",", 1)
                    metros.append({"area": city.strip(), "state": s.strip() or st})
    # dedupe
    seen = set(); out = []
    for m in metros:
        k = (m["area"], m["state"])
        if k not in seen and m["area"]:
            seen.add(k); out.append(m)
    return out

def strike(state="US", limit=8, dry=False, send=True):
    """Fire restoration+roofing outreach to storm-affected metros."""
    import advertising_agent as aa
    import outreach as oc
    metros = get_storm_metros(state, limit)
    real = [m for m in metros if "error" not in m]
    print(f"[storm-strike] {len(real)} storm metros: {[m['area'] for m in real]}")
    if not real:
        print("[storm-strike] no active alerts — standing down")
        return 0
    sent = 0
    for m in real:
        # pull contractors in the affected metro via empire-leads
        near = f"{m['area']}, {m['state']}"
        for vertical, copy in [("restoration", COPY_RESTORE), ("roofing", COPY_ROOF)]:
            try:
                pros = aa.get_prospects(vertical, limit=4)
                clean = [p for p in pros if "error" not in p]
                if not clean:
                    continue
                camp = {"pipeline": json.load(open(copy)), "prospects": clean}
                tf = f"/tmp/hermes-verify-storm-{m['area']}.json"
                json.dump(camp, open(tf, "w"))
                oc.run("both", vertical, limit=4, dry=dry, copy=tf,
                       storm=False)
                sent += len(clean)
                os.remove(tf)
            except Exception as e:
                print(f"[storm-strike] {vertical}@{near} err: {e}")
            time.sleep(10)  # avoid Overpass burst
    print(f"[storm-strike] done: {sent} contractor emails across {len(real)} storm zones")
    return sent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="US")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-send", dest="send", action="store_false")
    a = ap.parse_args()
    strike(a.state, a.limit, a.dry, a.send)
