"""
Empire OS v3 — Custom state contractor portal flows.

Generic form-fill fails on state licensing portals (hidden server-state
fields, 2-step reveals, JS handshakes). These are per-portal custom flows
that actually return rows:

  - fl_dbpr(term, city)   : FL Dept of Business & Professional Regulation
                            (real 2-step form, 306+ recs for "roofing")
  - bing_state(term, st)  : Bing-rendered fallback for CA/TX/any state
                            (CA CSLB is license-number based, not discovery)

Each returns list[dict] normalized to lead schema.
"""
import os, re, datetime
from typing import Optional

from empire_os.browser_tool import get_tool
from bs4 import BeautifulSoup

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def _norm(name, city, state, phone="", web="", lic="", source="", extra=""):
    return {
        "kind": "contractor",
        "name": name, "phone": phone, "email": "",
        "address": "", "city": city, "state": state, "postcode": "",
        "category": "", "website": web, "lat": None, "lon": None,
        "license_no": lic, "source": source, "extra": extra,
        "scraped_at": _now(),
    }


def fl_dbpr(term: str, city: str = "", limit: int = 25) -> list[dict]:
    """FL DBPR license search — custom 2-step flow."""
    rows: list[dict] = []
    tool = get_tool()
    pg = tool.new_page()
    try:
        pg.goto("https://www.myfloridalicense.com/wl11.asp",
                wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(1500)
        pg.check("input[name='SearchType'][value='Name']")
        pg.click("button[name='SelectSearchType']")
        pg.wait_for_timeout(2500)
        try:
            pg.fill("input[name='OrgName']", term)
        except Exception:
            pass
        try:
            pg.check("input[name='SearchPartName']")
        except Exception:
            pass
        try:
            pg.keyboard.press("Enter")
        except Exception:
            pass
        pg.wait_for_timeout(5000)
        soup = BeautifulSoup(pg.content(), "html.parser")
        for t in soup.find_all("table"):
            head = t.get_text(" ", strip=True)
            if "License Type" in head and "Search Results" not in head:
                for tr in t.find_all("tr")[1:]:
                    cells = tr.find_all("td")
                    if len(cells) < 2:
                        continue
                    a = cells[1].find("a")
                    if not a:
                        continue
                    name = cells[1].get_text(" ", strip=True) or (a.get_text(" ", strip=True) if a else "")
                    # FL result cell sometimes nests the name in the link + extra;
                    # take the full cell text, collapse spaces, drop the license id
                    name = re.sub(r"\s+", " ", name).strip()
                    if not name or len(name) < 2:
                        continue
                    href = a.get("href", "")
                    m = re.search(r"id=([A-F0-9]+)", href)
                    lic_id = m.group(1) if m else ""
                    status = cells[-1].get_text(" ", strip=True)
                    # pre-qualify: skip inactive statuses
                    bad = ("application in progress", "expired", "null", "void",
                           "revoked", "closed", "inactive", "delinquent")
                    if any(b in status.lower() for b in bad):
                        continue
                    lead = _norm(name, city, "FL", lic=lic_id,
                                source="fl_dbpr", extra=status)
                    # enrich with contact info from detail page (WARM -> HOT)
                    if href and len(rows) < 5:
                        d = _fl_detail(tool, str(href))
                        # real license no (CCC1333773) beats hex tracking id
                        if d.get("license_no_real"):
                            lead["license_no"] = d["license_no_real"]
                        st = d.pop("license_status_detail", "")
                        if st and not status:
                            lead["extra"] = st
                            lead["license_status"] = st
                        elif st:
                            lead["license_status"] = st
                        for k in ("city", "postcode", "license_type", "license_expires"):
                            if d.get(k) and not lead.get(k):
                                lead[k] = d[k]
                    rows.append(lead)
            if len(rows) >= limit:
                break
    except Exception as e:
        rows.append({"error": f"fl_dbpr: {e}"})
    finally:
        pg.close()
    return rows[:limit]


def _fl_detail(tool, href: str) -> dict:
    """Fetch FL license detail page → real license_no, status, city, postcode,
    license_type. Detail pages carry NO business phone/email/website (verified
    2026-08-24); contact enrichment happens downstream (enrichment v2)."""
    out = {"phone": "", "email": "", "website": ""}
    try:
        url = href if href.startswith("http") else "https://www.myfloridalicense.com/" + href
        html = tool.get_html(url, wait="domcontentloaded", extra_sleep=2)
        if not html or html.startswith("<error>"):
            return out
        soup = BeautifulSoup(html, "html.parser")
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

        # real license number, e.g. CCC1333773 / CVC56821 / CBC051234
        m = re.search(r"License Number\s+([A-Z]{2,4}\d{4,8})", text)
        if m:
            out["license_no_real"] = m.group(1)

        # status + expiry, e.g. "Status Current,Active Licensure Date ... Expires 08/31/2028"
        ms = re.search(r"Status\s+([^E]{3,40}?)\s+(?:Licensure|Expires)", text)
        if ms:
            out["license_status_detail"] = ms.group(1).strip()
        me = re.search(r"Expires\s+(\d{2}/\d{2}/\d{4})", text)
        if me:
            out["license_expires"] = me.group(1)
            out["license_status_detail"] = (out.get("license_status_detail", "") +
                                            " Expires " + me.group(1)).strip()

        # license type, e.g. "Certified Roofing Contractor"
        mt = re.search(r"License Type\s+([A-Za-z /]+Contractor|[A-Za-z /]+?)(?:\s+Rank|\s+License Number)", text)
        if mt:
            out["license_type"] = mt.group(1).strip()

        # mailing address → postcode + city extraction. FL format:
        # "Main Address 5100 SW 90 AV UNIT 411 COOPER CITY Florida 33318".
        # City = tokens AFTER last street suffix (AV/ST/DR...); unit markers
        # deleted, house number + leading directionals stripped.
        ma = re.search(r"(?:Mailing Address|Main Address)\s+(.*?)\s+Florida\s+(\d{5})", text)
        if ma:
            seg = re.sub(r"\s(?:UNIT|APT|STE|SUITE)\s+\S+", "", ma.group(1), flags=re.I)
            seg = re.sub(r"\s#\s*\d+", "", seg)
            seg = re.sub(r"^\s*#?\s*\d+\s+", "", seg)
            toks = seg.split()
            while toks and toks[0] in ("N", "S", "E", "W", "NE", "NW", "SE", "SW"):
                toks.pop(0)
            SUF = ("ST", "AVE", "AV", "WAY", "RD", "ROAD", "DR", "DRIVE", "BLVD",
                   "BOULEVARD", "LN", "LANE", "CT", "COURT", "HWY", "HIGHWAY",
                   "TER", "TERRACE", "PL", "PLACE", "CIR", "CIRCLE", "TRL", "TRAIL")
            last = -1
            for i, tok in enumerate(toks):
                t = tok.upper()
                if t in SUF or re.match(r"^\d+(ST|ND|RD|TH)$", t):
                    last = i
            tail = toks[last + 1:]
            while len(tail) > 1 and tail[0] in ("NORTH", "SOUTH", "EAST", "WEST"):
                tail.pop(0)
            out["city"] = " ".join(tail) if tail else ""
            out["postcode"] = ma.group(2)
    except Exception:
        pass
    return out


def bing_state(term: str, state: str, city: str = "", limit: int = 15) -> list[dict]:
    """Bing-rendered state contractor discovery (CA/TX fallback)."""
    rows: list[dict] = []
    tool = get_tool()
    q = f"{term} contractors {'in '+city if city else ''} {state}".strip()
    try:
        import urllib.parse
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=20"
        html = tool.get_html(url, wait="domcontentloaded", extra_sleep=2)
        if not html or html.startswith("<error>"):
            return rows
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("li.b_algo")[:limit]:
            name_el = card.select_one("h2 a")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 3:
                continue
            cap = card.select_one("div.b_caption p, div.b_lineclamp")
            text = cap.get_text(" ", strip=True) if cap else ""
            m = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
            web = name_el.get("href", "") if name_el else ""
            rows.append(_norm(name, city, state, phone=m.group(0) if m else "",
                              web=web, source="bing_state"))
    except Exception as e:
        rows.append({"error": f"bing_state: {e}"})
    return rows[:limit]
