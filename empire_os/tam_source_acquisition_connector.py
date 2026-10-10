"""EmpireOS existing-entity source acquisition bridge (read-only, fail-closed).

A verified public-source observation is NOT proof of canonical identity, buyer
intent, consent or authority to append an acquisition. Store proposals privately
for identity review. The established atomic writer handles *new* prospects;
this bridge never calls it for already linked prospects.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit

SECTORS = frozenset({"solar", "roofing"})
COUNTRIES = frozenset({"GB", "US"})
SOURCES = frozenset({"recc_solar", "overpass_osm"})
MAX_TARGETS = 500
MAX_SOURCE = 40
MAX_RECC_PAGE = 40  # at most 41 public listing pages; 40 details/page

TARGET_SQL = """
WITH targets AS MATERIALIZED (
    SELECT e.id, e.canonical_name, e.canonical_niche,
      e.canonical_website,e.canonical_phone
    FROM public.business_entities e
    WHERE lower(btrim(e.canonical_niche))=%s
      AND btrim(e.canonical_name)<>''
      AND EXISTS (
        SELECT 1 FROM public.prospect_entity_links l
        WHERE l.entity_id=e.id AND l.active IS TRUE
      )
      AND NOT EXISTS (
        SELECT 1 FROM public.prospect_entity_links l
        JOIN public.prospect_acquisitions a ON a.prospect_id=l.prospect_id
        WHERE l.entity_id=e.id AND l.active IS TRUE
      )
    ORDER BY e.id LIMIT %s
)
SELECT t.id::text,t.canonical_name,t.canonical_niche,
  t.canonical_website,t.canonical_phone,
  l.prospect_id::text,p.website
FROM targets t
JOIN public.prospect_entity_links l
  ON l.entity_id=t.id AND l.active IS TRUE
JOIN public.prospects p ON p.id=l.prospect_id
ORDER BY t.id,l.prospect_id
"""


def _clean_name(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _digits(value: Any) -> str:
    d = re.sub(r"\D", "", str(value or ""))
    return d if 10 <= len(d) <= 15 else ""


def _phone_key(value: Any, country: str) -> str:
    """Normalize *supported* national/international formats, never guess."""
    digits=_digits(value)
    if not digits:
        return ""
    if country=="GB":
        if digits.startswith("0044") and len(digits)==14:
            digits=digits[2:]
        if digits.startswith("0") and len(digits)==11:
            digits="44"+digits[1:]
        return digits if digits.startswith("44") and len(digits)==12 else ""
    if country=="US":
        if len(digits)==10:
            digits="1"+digits
        return digits if digits.startswith("1") and len(digits)==11 else ""
    return ""


def _host(value: Any) -> str:
    try:
        u = urlsplit(str(value or "").strip())
        if u.scheme not in ("http", "https") or not u.hostname:
            return ""
        hostname = u.hostname.casefold().removeprefix("www.")
        if (u.username or u.password or u.port not in (None, 80, 443)
                or hostname in ("localhost", "127.0.0.1")):
            return ""
        return hostname
    except (ValueError, TypeError):
        return ""


def _provenance(value: Any, source: str) -> str:
    raw = str(value or "").strip()
    try:
        u = urlsplit(raw)
    except ValueError:
        return ""
    if u.scheme != "https" or u.username or u.password or u.fragment:
        return ""
    if source == "recc_solar":
        return raw if (_host(raw) == "recc.org.uk"
                       and u.path.startswith("/scheme/members/")
                       and len(u.path) > len("/scheme/members/")) else ""
    if source == "overpass_osm":
        return raw if (_host(raw) == "openstreetmap.org"
                       and re.fullmatch(r"/(node|way|relation)/[0-9]+",u.path)
                       and not u.query) else ""
    return ""


def validate_scope(*, source: str, sector: str, country: str,
                   limit: int) -> None:
    if (source not in SOURCES or sector not in SECTORS or
        country not in COUNTRIES or type(limit) is not int
        or not 1 <= limit <= MAX_TARGETS or
        (source == "recc_solar" and (sector,country)!=("solar","GB"))):
        raise ValueError("source acquisition scope not approved")


def canonical_targets(dsn: str, *, sector: str, limit: int = 250,
                      connect_factory: Callable | None = None) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= MAX_TARGETS:
        raise ValueError("invalid source target limit")
    if sector not in SECTORS:
        raise ValueError("unsupported source target sector")
    from psycopg.conninfo import conninfo_to_dict
    try:
        cfg = conninfo_to_dict(dsn)
    except Exception as exc:
        raise ValueError("invalid canonical database connection") from exc
    if (cfg.get("dbname")!="empiredb" or
        cfg.get("host") not in (None,"127.0.0.1","localhost",
                               "/var/run/postgresql") or
        cfg.get("service") or cfg.get("hostaddr")):
        raise ValueError("source connector requires local canonical EmpireDB")
    if connect_factory is None:
        import psycopg
        connect_factory = lambda c: psycopg.connect(c,connect_timeout=5)
    try:
        with connect_factory(dsn) as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='12000ms'")
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != "empiredb":
                    raise RuntimeError("not canonical EmpireDB")
                cur.execute(TARGET_SQL,(sector,limit))
                rows=cur.fetchall()
    except Exception:
        raise RuntimeError("canonical source-target read unavailable") from None
    if len(rows) > limit*50:
        raise RuntimeError("source-target relationship fanout unsafe")
    return [{
        "entity_id":r[0],"canonical_name":r[1],"sector":r[2],
        "canonical_website":r[3],"canonical_phone":r[4],
        "prospect_id":r[5],"prospect_website":r[6],
    } for r in rows]


def source_observations(*, source: str, sector: str, country: str,
                        metro: str | None = None,
                        fetcher: Callable | None = None,
                        max_source: int = MAX_SOURCE,
                        source_page: int = 0) -> list[dict]:
    validate_scope(source=source,sector=sector,country=country,limit=1)
    if type(max_source) is not int or not 1 <= max_source <= MAX_SOURCE:
        raise ValueError("source observation bound invalid")
    if type(source_page) is not int or not 0 <= source_page <= MAX_RECC_PAGE:
        raise ValueError("RECC source page outside bounded research scope")
    if source == "recc_solar":
        if metro not in (None, ""):
            raise ValueError("RECC is national, not a metro source")
        if source_page and fetcher is not None:
            raise ValueError("custom RECC adapter cannot fake paginated source")
        if source_page:
            from empire_os.lead_sources import recc_solar
            from urllib.parse import urlencode
            query=urlencode({
                "technology":"Solar PV", "submitbutton":"submit",
                "page":str(source_page),
            })
            try:
                listing=recc_solar._get(recc_solar.SEARCH_URL+"?"+query)
                members=recc_solar._member_links(listing,limit=max_source)
            except Exception:
                raise RuntimeError("real paginated RECC listing failed") from None
            def paged_members():
                for url,name in members:
                    try:
                        item=recc_solar._detail(name,url)
                    except Exception:
                        continue
                    if item is not None:
                        yield item
            iterable=paged_members()
        else:
            if fetcher is None:
                from empire_os.lead_sources.recc_solar import run
                fetcher = run
            try:
                iterable=fetcher(metro=None)
            except Exception:
                raise RuntimeError("real public-source acquisition probe failed") from None
    else:
        if source_page:
            raise ValueError("source pagination is RECC-only")
        from empire_os.geo_registry import market_by_metro
        from empire_os.lead_sources.overpass import METRO_COORDS,run
        market=market_by_metro(metro) if metro else None
        if metro not in METRO_COORDS or market is None or market.country_code != country:
            raise ValueError("Overpass requires an approved country-matched metro")
        if fetcher is None:
            fetcher = run
        try:
            iterable=fetcher(metro=metro)
        except Exception:
            raise RuntimeError("real public-source acquisition probe failed") from None
    observed=[]
    try:
        for item in iterable:
            if len(observed) >= max_source:
                break
            obj=item if isinstance(item,Mapping) else vars(item)
            raw=obj.get("raw")
            origin=str(obj.get("source") or "").strip()
            url=_provenance(obj.get("url"),source)
            if origin != source or not url:
                continue
            if str(obj.get("niche") or "").casefold()!=sector:
                continue
            if str(obj.get("country_code") or "").upper()!=country:
                continue
            name=str(obj.get("name") or "").strip()
            if not _clean_name(name):
                continue
            observed.append({
                "name":name,
                "sector":sector,
                "country_code":country,
                "source":source,
                "source_url":url,
                "business_website":(raw or {}).get("business_website")
                    if isinstance(raw,Mapping) else "",
                "phone":obj.get("phone"),
                "metro":obj.get("metro"),
            })
    except Exception:
        raise RuntimeError("real public-source acquisition probe failed") from None
    return observed


def _identity_domain(value: Any) -> str:
    """Only a business-owned host can corroborate identity."""
    host = _host(value)
    if host in {
        "facebook.com", "instagram.com", "linkedin.com", "x.com",
        "twitter.com", "youtube.com", "tiktok.com", "wixsite.com",
        "wordpress.com", "sites.google.com", "linktr.ee",
    } or host.endswith((".facebook.com", ".instagram.com",
                        ".linkedin.com", ".wixsite.com",
                        ".wordpress.com")):
        return ""
    return host


def build_review(*, targets: Iterable[Mapping], observations: Iterable[Mapping],
                 source: str, sector: str, country: str) -> dict:
    validate_scope(source=source,sector=sector,country=country,limit=1)
    target_rows = {}
    for row in targets:
        if row.get("sector")!=sector:
            continue
        entity = str(row.get("entity_id") or "").strip()
        prospect = str(row.get("prospect_id") or "").strip()
        name = _clean_name(row.get("canonical_name"))
        if entity and prospect and name:
            # Eliminate repeated relationship rows in a join result, but
            # preserve genuinely distinct prospect/entity associations.
            key=(entity,prospect)
            target_rows.setdefault(key,dict(row))
    values=list(target_rows.values())
    name_index=defaultdict(set)
    domain_index=defaultdict(set)
    phone_index=defaultdict(set)
    for key,row in target_rows.items():
        name_index[_clean_name(row["canonical_name"])].add(key)
        for field in ("canonical_website","prospect_website"):
            domain=_identity_domain(row.get(field))
            if domain:
                domain_index[domain].add(key)
        phone=_phone_key(row.get("canonical_phone"),country)
        if phone:
            phone_index[phone].add(key)

    observed=list(observations)
    findings=[]
    for o in observed:
        if (o.get("source")!=source or o.get("sector")!=sector
                or o.get("country_code")!=country
                or not _provenance(o.get("source_url"),source)):
            continue
        clean_name=_clean_name(o.get("name"))
        if not clean_name:
            continue
        source_domain=_identity_domain(o.get("business_website"))
        phone=_phone_key(o.get("phone"),country)
        by_name=name_index.get(clean_name,set())
        by_domain=domain_index.get(source_domain,set()) if source_domain else set()
        by_phone=phone_index.get(phone,set()) if phone else set()
        match_keys=by_name|by_domain|by_phone
        if not match_keys:
            continue
        names={target_rows[k]["entity_id"] for k in by_name}
        domains={target_rows[k]["entity_id"] for k in by_domain}
        phones={target_rows[k]["entity_id"] for k in by_phone}
        entities={target_rows[k]["entity_id"] for k in match_keys}
        prospects={target_rows[k]["prospect_id"] for k in match_keys}
        has_name=bool(by_name)
        has_domain=bool(by_domain)
        has_phone=bool(by_phone)

        conflicting_domain=bool(
            has_name and source_domain and
            any(_identity_domain(target_rows[k].get(field))
                and _identity_domain(target_rows[k].get(field)) != source_domain
                for k in by_name
                for field in ("canonical_website","prospect_website"))
        )
        contradictory_signals=bool(
            (names and domains and names != domains)
            or (names and phones and names != phones)
            or (domains and phones and domains != phones)
        )
        strong=(len(entities)==1 and len(prospects)==1
                and has_name and (has_domain or has_phone)
                and not conflicting_domain and not contradictory_signals)
        if len(entities)!=1:
            state="AMBIGUOUS_IDENTITY"
        elif len(prospects)!=1:
            state="AMBIGUOUS_PROSPECT_RELATIONSHIP"
        elif contradictory_signals:
            state="CONFLICTING_IDENTITY_SIGNALS"
        elif conflicting_domain:
            state="CONFLICTING_WEBSITE"
        elif strong:
            state="STRONG_EVIDENCE_REVIEW"
        elif has_name:
            state="NAME_ONLY_REVIEW"
        elif has_domain and has_phone:
            state="NAME_VARIANT_DOMAIN_PHONE_REVIEW"
        elif has_domain:
            state="NAME_VARIANT_DOMAIN_REVIEW"
        else:
            state="NAME_VARIANT_PHONE_REVIEW"
        basis=(["exact_name"] if has_name else [])
        basis+=["independent_website_host"] if has_domain else []
        basis+=["independent_phone"] if has_phone else []
        findings.append({
            "state":state,
            "match_basis":basis,
            "candidate_name":o["name"],
            "country_code":country,
            "sector":sector,
            "source":source,
            "source_url":o["source_url"],
            "entity_ids":sorted(entities),
            "prospect_ids":sorted(prospects),
            "attachment_review_id":sha256(json.dumps({
                "entity_ids":sorted(entities),
                "prospect_ids":sorted(prospects),
                "source":source,"source_url":o["source_url"],
            },sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "proposed_source_evidence":{
                "source":source,"source_url":o["source_url"],
                "locale":{"country_code":country},
                "identity_match_basis":basis,
                "source_ref_verified_on_public_page":False,
            },
            "external_write_authorized":False,
            "canonical_acquisition_appended":False,
            "buyer_intent_inferred":False,
            "identity_verified_for_automatic_promotion":False,
        })
    matched_by_entity=Counter(eid for f in findings for eid in f["entity_ids"])
    matched_by_source=Counter(f["source_url"] for f in findings)
    for finding in findings:
        if (any(matched_by_entity[eid]>1 for eid in finding["entity_ids"])
                or matched_by_source[finding["source_url"]]>1):
            finding["state"]="AMBIGUOUS_MULTI_SOURCE_OR_ENTITY"

    return {
        "schema_version":"empire.tam-source-acquisition-review.v1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "mode":"OBSERVE",
        "source":source,"sector":sector,"country_code":country,
        "target_relationship_rows_examined":len(values),
        "unique_target_entities_examined":len({x["entity_id"] for x in values}),
        "unique_target_prospects_examined":len({x["prospect_id"] for x in values}),
        "target_entities_with_website_evidence":len({
            x["entity_id"] for x in values
            if _identity_domain(x.get("canonical_website"))
                or _identity_domain(x.get("prospect_website"))
        }),
        "target_entities_with_phone_evidence":len({
            x["entity_id"] for x in values
            if _phone_key(x.get("canonical_phone"),country)
        }),
        "source_observations_examined":len(observed),
        "source_observations_with_website":sum(bool(
            _identity_domain(x.get("business_website"))) for x in observed),
        "source_observations_with_phone":sum(bool(
            _phone_key(x.get("phone"),country)) for x in observed),
        "potential_matched_observations":len(findings),
        "strong_evidence_review_count":sum(
            f["state"]=="STRONG_EVIDENCE_REVIEW" for f in findings),
        "name_variant_review_count":sum(
            f["state"].startswith("NAME_VARIANT_") for f in findings),
        "manual_review_count":sum(f["state"]!="STRONG_EVIDENCE_REVIEW"
                                  for f in findings),
        "findings":findings,
        "genuine_acquisition_appended":0,
        "database_write":False,
        "customer_contact_attempted":False,
        "outbound_sent":False,
        "execution_authority":"none",
        "tam_market_population_verified":False,
        "source_observation_is_not_automatic_identity_proof":True,
    }
