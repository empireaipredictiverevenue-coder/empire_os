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
import ipaddress
import re
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit

SECTORS = frozenset({"solar", "roofing"})
COUNTRIES = frozenset({"GB", "US"})
SOURCES = frozenset({"recc_solar", "overpass_osm", "first_party_site", "first_party_search"})
MAX_TARGETS = 500
MAX_SOURCE = 40
MAX_RECC_PAGE = 40  # at most 41 public listing pages; 40 details/page

TARGET_SQL = """
WITH targets AS MATERIALIZED (
    SELECT e.id, e.canonical_name, e.canonical_niche,
      e.canonical_website,e.canonical_phone,e.canonical_metro
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
  l.prospect_id::text,p.website,p.phone,p.business_name,
  t.canonical_metro
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
        (source in {"recc_solar","first_party_site","first_party_search"}
            and (sector,country)!=("solar","GB"))):
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
        "prospect_phone":r[7],"prospect_name":r[8],
        "canonical_metro":r[9],
    } for r in rows]


def source_observations(*, source: str, sector: str, country: str,
                        metro: str | None = None,
                        fetcher: Callable | None = None,
                        max_source: int = MAX_SOURCE,
                        source_page: int = 0) -> list[dict]:
    validate_scope(source=source,sector=sector,country=country,limit=1)
    if type(max_source) is not int or not 1 <= max_source <= MAX_SOURCE:
        raise ValueError("source observation bound invalid")
    if source in {"first_party_site","first_party_search"}:
        raise ValueError("first-party evidence must use target-bound research")
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
        for field in ("canonical_phone", "prospect_phone"):
            phone=_phone_key(row.get(field),country)
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
        "target_entities_with_linked_prospect_phone":len({
            x["entity_id"] for x in values
            if _phone_key(x.get("prospect_phone"),country)
        }),
        "target_prospects_with_linked_phone":len({
            x["prospect_id"] for x in values
            if _phone_key(x.get("prospect_phone"),country)
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


def build_first_party_site_review(
    *, targets: Iterable[Mapping[str, Any]],
    max_sites: int = 5,
    site_probe: Callable | None = None,
    diagnose_only: bool = False,
) -> dict[str, Any]:
    """Conservatively inspect owned-site *claims* for existing solar entities.

    No DB writes, country assertions or source acquisition admissions.
    A single first-party website seen on ten prospect rows is still only
    a candidate *entity-level* source. All records remain founder-review.
    """
    if type(max_sites) is not int or not 1 <= max_sites <= 5:
        raise ValueError("first-party probe is limited to five business websites")
    if type(diagnose_only) is not bool:
        raise ValueError("invalid diagnostics mode")
    if site_probe is None and not diagnose_only:
        from empire_os.search_fabric.site_probe import probe_site
        site_probe = probe_site

    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in targets:
        if row.get("sector") != "solar":
            continue
        entity = str(row.get("entity_id") or "").strip()
        prospect = str(row.get("prospect_id") or "").strip()
        name = _clean_name(row.get("canonical_name"))
        if not entity or not prospect or not name:
            continue
        by_entity[entity].append(dict(row))

    hosts: dict[str, str] = {}
    candidate_url: dict[str, str] = {}
    disqualified: dict[str, str] = {}
    entities_with_candidate_url = 0
    candidate_url_rows = 0
    candidate_usable_website_rows = 0
    candidate_unusable_website_rows = 0
    candidate_path_urls = 0
    for entity, rows in by_entity.items():
        names = {_clean_name(r.get("canonical_name")) for r in rows}
        linked_names = {
            _clean_name(r.get("prospect_name"))
            for r in rows if str(r.get("prospect_name") or "").strip()
        }
        if len(names) != 1 or (linked_names and linked_names != names):
            disqualified[entity] = "CONFLICTING_CANONICAL_OR_PROSPECT_NAMES"
            continue
        found: set[str] = set()
        urls: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            for key in ("canonical_website", "prospect_website"):
                value = str(row.get(key) or "").strip()
                if not value:
                    continue
                candidate_url_rows += 1
                host = _identity_domain(value)
                if not host:
                    candidate_unusable_website_rows += 1
                    continue
                try:
                    parsed = urlsplit(value)
                    if (parsed.scheme not in ("http", "https")
                            or parsed.username or parsed.password
                            or parsed.query or parsed.fragment):
                        candidate_unusable_website_rows += 1
                        continue
                    # A site's /about or /contact URL may still identify
                    # its public host. Probe its root, NOT that deep path.
                    if parsed.path not in ("", "/"):
                        candidate_path_urls += 1
                except (ValueError, TypeError):
                    candidate_unusable_website_rows += 1
                    continue
                if (not re.fullmatch(r"[a-z0-9.-]+", host)
                        or host.endswith((".local", ".internal", ".localhost",
                                          ".test", ".invalid", ".onion"))
                        or host in ("co.uk", "org.uk", "com", "net", "org")
                        or host.startswith(".") or "." not in host):
                    continue
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    pass
                else:
                    continue
                found.add(host)
                candidate_usable_website_rows += 1
                urls[host].append(value)
        if found:
            entities_with_candidate_url += 1
        if len(found) != 1:
            disqualified[entity] = (
                "NO_UNAMBIGUOUS_BUSINESS_WEBSITE" if not found
                else "CONFLICTING_BUSINESS_WEBSITE_HOSTS"
            )
            continue
        host = next(iter(found))
        hosts[entity] = host
        candidate_url[entity] = "https://" + host + "/"

    entity_candidates_before_shared_host_filter = len(hosts)
    shared_hosts = Counter(hosts.values())
    shared_host_entity_count = sum(
        1 for host in hosts.values() if shared_hosts[host] > 1
    )
    shared_host_distinct_count = sum(
        1 for n in shared_hosts.values() if n > 1
    )
    for entity, host in list(hosts.items()):
        if shared_hosts[host] != 1:
            disqualified[entity] = "BUSINESS_HOST_SHARED_ACROSS_ENTITIES"
            del hosts[entity]
            candidate_url.pop(entity, None)

    findings: list[dict[str, Any]] = []
    selected = [] if diagnose_only else sorted(hosts)[:max_sites]
    for entity in selected:
        host = hosts[entity]
        rows = by_entity[entity]
        requested_url = candidate_url[entity]
        try:
            data = site_probe(
                requested_url,
                max_pages=2, request_timeout=4.0,
                time_budget_seconds=10.0, public_only=True,
            )
        except Exception:
            data = {}
        verified_host = (
            isinstance(data, Mapping)
            and data.get("ok") is True
            and _identity_domain(data.get("final_url")) == host
            and data.get("final_url", "").startswith("https://")
            and isinstance(data.get("pages_checked"), list)
            and len(data["pages_checked"]) >= 1
            and any(
                isinstance(page, Mapping)
                and _identity_domain(page.get("url")) == host
                for page in data["pages_checked"]
            )
        )
        observed_names = (
            data.get("business_names") if isinstance(data, Mapping) else []
        )
        if not isinstance(observed_names, list):
            observed_names = []
        name_supported = verified_host and any(
            _clean_name(x) == _clean_name(rows[0]["canonical_name"])
            for x in observed_names if isinstance(x, str)
        )
        state = (
            "FIRST_PARTY_NAME_EVIDENCE_REVIEW" if name_supported
            else "FIRST_PARTY_SITE_OBSERVED_NAME_UNVERIFIED" if verified_host
            else "FIRST_PARTY_PROBE_UNAVAILABLE_OR_UNTRUSTED"
        )
        findings.append({
            "entity_id": entity,
            "linked_prospect_count": len({
                str(r["prospect_id"]) for r in rows
            }),
            "canonical_name": rows[0]["canonical_name"],
            "review_state": state,
            "first_party_host": host,
            "source_url": data.get("final_url") if verified_host else None,
            "observed_business_names": [
                n for n in observed_names if isinstance(n, str)
            ][:6] if verified_host else [],
            "observed_business_addresses": [
                a for a in data.get("addresses", [])
                if isinstance(a, str)
            ][:4] if verified_host and isinstance(data.get("addresses"), list) else [],
            "homepage_fetched": bool(verified_host),
            "country_explicitly_verified": False,
            "canonical_resolution_verified": False,
            "prospect_attachment_authorized": False,
            "acquisition_appended": False,
            "source_provenance_verified_for_ledger": False,
        })
    return {
        "schema_version": "empire.tam-first-party-source-review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "sector": "solar",
        "country_research_focus": "GB",
        "country_verified_from_site": False,
        "source": "first_party_site",
        "entities_considered": len(by_entity),
        "entities_with_unique_business_host": len(hosts),
        "entities_skipped_for_ambiguous_identity_or_domain": len(disqualified),
        "eligibility_diagnostic": {
            "rejection_reasons": dict(sorted(Counter(
                disqualified.values()
            ).items())),
            "entity_candidates_before_cross_entity_host_check":
                entity_candidates_before_shared_host_filter,
            "entities_with_any_valid_candidate_host": entities_with_candidate_url,
            "unique_candidate_host_count": len(shared_hosts),
            "cross_entity_shared_host_entity_count":
                shared_host_entity_count,
            "cross_entity_shared_host_distinct_count":
                shared_host_distinct_count,
            "candidate_website_values_examined": candidate_url_rows,
            "eligible_website_values": candidate_usable_website_rows,
            "unusable_website_values": candidate_unusable_website_rows,
            "website_values_with_path": candidate_path_urls,
        },
        "diagnose_only": diagnose_only,
        "site_probe_limit": max_sites,
        "site_probes_attempted": len(selected),
        "sites_retrieved_from_expected_host": sum(
            f["homepage_fetched"] for f in findings
        ),
        "sites_supporting_exact_canonical_name": sum(
            f["review_state"] == "FIRST_PARTY_NAME_EVIDENCE_REVIEW"
            for f in findings
        ),
        "findings": findings,
        "database_write": False,
        "acquisitions_appended": 0,
        "outbound_sent": False,
        "buyer_intent_inferred": False,
        "execution_authority": "none",
        "tam_population_verified": False,
    }


def build_first_party_discovery_review(
    *, targets: Iterable[Mapping[str, Any]], max_entities: int = 3,
    searcher: Callable | None = None, site_probe: Callable | None = None,
) -> dict[str, Any]:
    """Find candidate first-party domains independently of polluted website field.

    Search/website signals are review hints, not company verification or
    authority to choose any one prospect for an acquisition ledger record.
    """
    if type(max_entities) is not int or not 1 <= max_entities <= 5:
        raise ValueError("first-party discovery limited to five entities")
    if searcher is None:
        from empire_os.search_fabric.reliable_search import search_reliable_rows
        searcher=search_reliable_rows
    if site_probe is None:
        from empire_os.search_fabric.site_probe import probe_site
        site_probe=probe_site
    from empire_os.search_fabric.verification import is_directory_url
    from empire_os.search_fabric.identity_guard import assess_first_party_identity

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    original_host_to_entities: dict[str, set[str]] = defaultdict(set)
    for r in targets:
        entity=str(r.get("entity_id") or "").strip()
        prospect=str(r.get("prospect_id") or "").strip()
        if r.get("sector")!="solar" or not entity or not prospect:
            continue
        grouped[entity].append(dict(r))
        for field in ("prospect_website","canonical_website"):
            host=_identity_domain(r.get(field))
            if host:
                original_host_to_entities[host].add(entity)
    shared_existing_hosts={
        host for host,owners in original_host_to_entities.items()
        if len(owners)>1
    }
    selected=[]
    skipped=Counter()
    for entity,rows in sorted(grouped.items()):
        names={_clean_name(r.get("canonical_name")) for r in rows}
        linked_names={_clean_name(r.get("prospect_name"))
                      for r in rows if str(r.get("prospect_name") or "").strip()}
        metros={str(r.get("canonical_metro") or "").strip() for r in rows}
        if len(names)!=1 or not next(iter(names), ""):
            skipped["CONFLICTING_OR_EMPTY_CANONICAL_NAMES"]+=1
            continue
        if linked_names and linked_names!=names:
            skipped["CONFLICTING_LINKED_PROSPECT_NAMES"]+=1
            continue
        if len(metros)!=1:
            skipped["CONFLICTING_CANONICAL_METRO"]+=1
            continue
        name=str(rows[0].get("canonical_name") or "").strip()
        metro=next(iter(metros))
        if not 8<=len(name)<=100 or not 2<=len(_clean_name(name).split())<=12:
            skipped["INSUFFICIENT_DISTINCTIVE_SEARCH_IDENTITY"]+=1
            continue
        if len(selected)<max_entities:
            selected.append((entity,name,metro,len({
                str(r["prospect_id"]) for r in rows
            })))
    candidate_by_entity={}
    search_errors=0
    discovered=0
    for entity,name,metro,prospect_count in selected:
        # A recorded metro disambiguates a search but NEVER proves geography.
        clean_metro=" ".join(re.findall(r"[A-Za-z0-9 -]+",metro))[:60]
        q=f'"{name}" {clean_metro} solar company official website'
        try:
            rows=searcher(q,num=5)
        except Exception:
            rows=[]
            search_errors+=1
        candidates={}
        if isinstance(rows,list):
            for row in rows[:5]:
                if not isinstance(row,Mapping):
                    continue
                url=str(row.get("link") or "").strip()
                host=_identity_domain(url)
                if (not host or host in shared_existing_hosts
                    or (host in original_host_to_entities
                        and entity not in original_host_to_entities[host])
                    or is_directory_url(url)
                    or host in ("recc.org.uk", "openstreetmap.org")
                    or host.endswith((".recc.org.uk", ".openstreetmap.org"))):
                    continue
                try:
                    parsed=urlsplit(url)
                    if (parsed.scheme!="https"
                        or parsed.username or parsed.password
                        or parsed.port not in (None,443)
                        or parsed.query or parsed.fragment):
                        continue
                except ValueError:
                    continue
                if not re.fullmatch(r"[a-z0-9.-]+",host) or "." not in host:
                    continue
                if (host.endswith((".local",".internal",".test",".invalid",".onion"))
                    or host in ("co.uk","org.uk","com","net","org")):
                    continue
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    pass
                else:
                    continue
                candidates.setdefault(host,"https://"+host+"/")
        discovered+=len(candidates)
        candidate_by_entity[entity]={
            "name":name,"metro":metro,"prospect_count":prospect_count,
            "domains":candidates,
        }
    host_to_entities=defaultdict(set)
    for entity,data in candidate_by_entity.items():
        for host in data["domains"]:
            host_to_entities[host].add(entity)
    findings=[]
    probes=0
    for entity,data in candidate_by_entity.items():
        unique_hosts=[
            host for host in data["domains"]
            if len(host_to_entities[host])==1
        ]
        # Any multiple plausible hosts are ambiguous. No first-result trust.
        if len(unique_hosts)!=1:
            findings.append({
                "entity_id":entity,
                "review_state":"AMBIGUOUS_OR_MISSING_DISCOVERED_HOST",
                "source_url":None,
                "linked_prospect_count":data["prospect_count"],
                "proven_country":False,
                "acquisition_appended":False,
            })
            continue
        host=unique_hosts[0]
        url=data["domains"][host]
        try:
            probes+=1
            probe=site_probe(url,max_pages=2,request_timeout=4.0,
                              time_budget_seconds=10.0,public_only=True)
        except Exception:
            probe={}
        safe=(isinstance(probe,Mapping)
              and probe.get("ok") is True
              and _identity_domain(probe.get("final_url"))==host
              and str(probe.get("final_url") or "").startswith("https://")
              and isinstance(probe.get("pages_checked"),list)
              and any(isinstance(x,Mapping) and
                      _identity_domain(x.get("url"))==host
                      for x in probe["pages_checked"]))
        accepted=False
        if safe:
            try:
                verdict=assess_first_party_identity(
                    prospect={
                        "business_name":data["name"],
                        "metro":data["metro"],
                        "niche":"solar",
                        "website":"",
                    },
                    candidate_url=url,probe=dict(probe),
                )
                accepted=bool(verdict.get("accepted")) and any(
                    _clean_name(n)==_clean_name(data["name"])
                    for n in probe.get("business_names",[])
                    if isinstance(n,str)
                )
            except Exception:
                accepted=False
        findings.append({
            "entity_id":entity,
            "canonical_name":data["name"],
            "linked_prospect_count":data["prospect_count"],
            "review_state":(
                "DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW"
                if accepted else "DISCOVERED_SITE_IDENTITY_UNVERIFIED"
            ),
            "source_url":url if safe else None,
            "observed_business_names":(
                [n for n in probe.get("business_names",[])
                 if isinstance(n,str)][:4]
                if safe else []
            ),
            "proven_country":False,
            "canonical_resolution_verified":False,
            "individual_prospect_link_verified":False,
            "acquisition_appended":False,
        })
    return {
        "schema_version":"empire.tam-first-party-discovery-review.v1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "mode":"OBSERVE",
        "source":"first_party_search",
        "sector":"solar",
        "country_research_focus":"GB",
        "entity_candidates_available":len(grouped),
        "entities_selected_for_search":len(selected),
        "search_errors":search_errors,
        "search_candidates_before_cross_entity_filter":discovered,
        "shared_existing_host_count":len(shared_existing_hosts),
        "entities_skipped_by_search_selector":dict(sorted(skipped.items())),
        "website_probes_attempted":probes,
        "verified_company_site_review_count":sum(
            x["review_state"]=="DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW"
            for x in findings
        ),
        "findings":findings,
        "database_write":False,
        "acquisitions_appended":0,
        "country_verified":False,
        "outbound_sent":False,
        "execution_authority":"none",
        "buyer_intent_inferred":False,
        "tam_population_verified":False,
    }
