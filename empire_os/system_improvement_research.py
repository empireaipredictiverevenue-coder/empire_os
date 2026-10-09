"""Research-first system improvement across EmpireOS workstreams.

Uses canonical capability registry + owned Search Fabric. Research is always
OBSERVE and findings require human/engineering verification before action.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ast
import hashlib
import ipaddress
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from empire_os.completion_capability_registry import build_completion_capability_registry
from empire_os.search_fabric.search import search_resilient

OUTPUT = Path("runtime/system_improvement/research")
PHASES = ("official_standards", "architecture_comparison", "evaluation_methods")
PRIORITY = ("opportunity_factory", "buyer_acquisition", "revenue_truth",
            "conversation_closer", "data_cloud", "fulfilment_outcomes")
SEARCH_RESULTS_LIMIT = 3
OFFICIAL_DOCUMENT_DOMAINS = (
    "nist.gov", "w3.org", "owasp.org", "ico.org.uk",
    "gov.uk", "cisa.gov", "developers.google.com",
    "sre.google", "oecd.org", "cloud.google.com",
)


def load(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def timestamp(text: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError):
        return None


def query_for(row: Mapping[str, Any], phase: str) -> str:
    topic = str(row.get("name") or row["key"]).split("/")[0].strip().lower()
    key = str(row["key"])
    if phase == "official_standards":
        if key in {"outreach_deliverability", "conversation_closer", "buyer_acquisition"}:
            return "ICO business to business direct marketing privacy guidance"
        return "NIST AI risk management framework measurement"
    if phase == "architecture_comparison":
        return "W3C provenance PROV-O entities activities sources"
    return f"{topic} evaluation metrics production testing"[:110]


def official_seed(row: Mapping[str, Any], phase: str) -> dict[str, str]:
    """Curated authoritative original documents; always fetch before claiming inspected."""
    owner = str(row.get("owner") or "")
    if phase == "official_standards":
        if owner in {"sales_revenue", "marketing_growth"}:
            return {
                "title": "ICO B2B direct marketing guidance",
                "url": "https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/",
            }
        return {
            "title": "NIST AI Risk Management Framework",
            "url": "https://www.nist.gov/itl/ai-risk-management-framework",
        }
    if phase == "architecture_comparison":
        return {"title": "W3C PROV Ontology Recommendation",
                "url": "https://www.w3.org/TR/prov-o/"}
    if owner in {"engineering", "operations_fulfilment"}:
        return {"title": "Google Site Reliability Engineering: Monitoring",
                "url": "https://sre.google/sre-book/monitoring-distributed-systems/"}
    return {
        "title": "Google Machine Learning: Precision and Recall",
        "url": "https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall",
    }


def citation(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    url = raw.get("link") or raw.get("url")
    title = str(raw.get("title") or "").strip()
    if not isinstance(url, str) or not title:
        return None
    try:
        p = urlsplit(url)
        domain = (p.hostname or "").lower()
        if p.scheme != "https" or not domain or p.username or p.password:
            return None
        if domain == "localhost" or domain.endswith(".local") or p.port not in (None, 443):
            return None
        try:
            ip = ipaddress.ip_address(domain)
            if not ip.is_global:
                return None
        except ValueError:
            pass
        clean = urlunsplit(("https", domain, p.path or "/", "", ""))
    except ValueError:
        return None
    if len(clean) > 700:
        return None
    return {"url": clean, "domain": domain, "title": title[:140],
            "retrieved_page_verified": False, "supports_business_outcome": False}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PageSummary(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.capture = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"title", "h1", "h2"}:
            self.capture = True

    def handle_endtag(self, tag):
        if tag.lower() in {"title", "h1", "h2"}:
            self.capture = False

    def handle_data(self, data):
        if self.capture and data.strip():
            self.parts.append(" ".join(data.split())[:130])


def inspect_primary_page(url: str) -> dict[str, Any]:
    """Bounded original-page check on allowlisted official domains only.

    Never follows cross-domain redirects or executes fetched content.
    """
    c = citation({"title": "source validation", "url": url})
    if c is None:
        return {"status": "UNSAFE_URL_REJECTED"}
    host = c["domain"]
    if not any(host == d or host.endswith("." + d)
               for d in OFFICIAL_DOCUMENT_DOMAINS):
        return {"status": "DISCOVERY_SOURCE_NOT_PRIMARY"}
    try:
        opener = build_opener(_NoRedirect())
        request = Request(c["url"], headers={"User-Agent": "EmpireOSResearch/1.0"})
        with opener.open(request, timeout=5) as response:
            content_type = response.headers.get_content_type()
            if content_type != "text/html":
                return {"status": "NOT_TEXT_HTML", "content_type": content_type}
            body = response.read(262_145)
        truncated = len(body) > 262_144
        body = body[:262_144]
        extracted = _PageSummary()
        extracted.feed(body.decode("utf-8", errors="replace"))
        headings = list(dict.fromkeys(extracted.parts))[:4]
        if not headings:
            return {"status": "NO_READABLE_HEADINGS"}
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "source_url": c["url"],
            "content_sha256": hashlib.sha256(body).hexdigest(),
            "hash_scope": "captured_prefix" if truncated else "full_response",
            "document_truncated": truncated,
            "document_headings": headings,
            "publication_date_verified": False,
            "claim_accuracy_verified": False,
        }
    except (OSError, ValueError) as error:
        return {"status": "DOCUMENT_ACCESS_UNAVAILABLE",
                "error_type": type(error).__name__}


def fingerprint(row: Mapping[str, Any]) -> str:
    data = [row["key"], row["checklist_pending"],
            sorted(row.get("module_evidence") or [])]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def source_audit(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    modules = [m for m in row.get("module_evidence") or [] if (root / m).is_file()]
    tests = []
    code_interfaces = {}
    for module in modules[:8]:
        stem = Path(module).stem
        test = root / "tests" / ("test_" + stem + ".py")
        if test.is_file():
            tests.append(str(test.relative_to(root)))
    for module in modules[:3]:
        try:
            source = (root / module).read_text(encoding="utf-8")
            tree = ast.parse(source)
            code_interfaces[module] = [
                n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ][:12]
        except (OSError, SyntaxError, UnicodeError):
            code_interfaces[module] = ["SOURCE_NOT_READABLE"]
    return {
        "workstream": row["key"], "owner": row["owner"],
        "name": row["name"], "checklist_pending": row["checklist_pending"],
        "checklist_done": row["checklist_done"],
        "source_module_count": len(modules), "module_examples": modules[:12],
        "source_interfaces_inspected": code_interfaces,
        "related_tests_discovered": tests,
        "tests_executed_by_research_agent": False,
        "pending_task_examples": (row.get("pending_items") or [])[:6],
        "runtime_verification": "NOT_PROVED_BY_CODE_INVENTORY",
        "economic_outcomes_proved": False,
    }


def dossier(row: Mapping[str, Any], entry: Mapping[str, Any], root: Path) -> dict[str, Any]:
    phases = entry.get("phases") or {}
    sources = []
    seen_urls = set()
    hosts = set()
    for phase in PHASES:
        for item in phases.get(phase, {}).get("sources", []):
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            hosts.add(item["domain"])
            sources.append(item)
    completed = all(p in phases and not phases[p].get("retry_required") for p in PHASES)
    inspected_hosts = {
        item["domain"] for item in sources
        if item.get("retrieved_page_verified") is True
    }
    ready = completed and len(inspected_hosts) >= 2
    return {
        "schema": "empire.system_research_dossier.v1",
        "workstream": row["key"],
        "audit": source_audit(root, row),
        "phases": {p: phases.get(p) for p in PHASES},
        "source_count": len(sources), "independent_domain_count": len(hosts),
        "primary_source_pages_checked": len(inspected_hosts),
        "citations_to_inspect": sources,
        "status": ("ORIGINAL_SOURCES_CHECKED_REVIEW_REQUIRED" if ready
                   else "RESEARCH_INCOMPLETE" if not completed
                   else "SOURCES_COLLECTED_PAGE_REVIEW_REQUIRED"),
        "comparison_questions": [
            "Which cited source practices are missing from the actual running workflow?",
            "Which modules implement only partial input-to-output plumbing?",
            "What runtime and negative-case tests would prove the claimed improvement?",
            "What business event would show measurable improvement without false positives?",
        ],
        "upgrade_hypotheses": [
            "Reconcile source, tests, dependencies and live operating evidence",
            "Benchmark source-backed alternatives against existing sovereign tools",
            "Implement only approved, scoped changes after an isolated rehearsal",
        ],
        "production_change_authorized": False, "outreach_authorized": False,
        "funds_authorized": False, "execution_authority": "none",
    }


def review_markdown(value: Mapping[str, Any]) -> str:
    """Human-readable research handoff; no unverified claim is promoted."""
    audit = value["audit"]
    lines = [
        "# EmpireOS Research Dossier — " + str(audit["name"]),
        "",
        "Status: **" + str(value["status"]) + "**",
        "Authority: OBSERVE; no automatic code, outbound, finance or deployment",
        "",
        "## Internal source and test inspection",
        "- Workstream: `" + str(value["workstream"]) + "`",
        "- Source modules found: " + str(audit["source_module_count"]),
        "- Checklist items pending: " + str(audit["checklist_pending"]),
        "- Exact-name related tests discovered: "
            + str(len(audit.get("related_tests_discovered") or [])),
        "- Runtime and revenue outcomes: NOT PROVED",
        "",
        "## External original-source research",
    ]
    for source in value.get("citations_to_inspect") or []:
        state = "original headings inspected" if source.get("retrieved_page_verified") else "source discovery only"
        lines.append("- " + source["title"] + " — " + source["url"] + " (" + state + ")")
        for heading in (source.get("page_inspection") or {}).get("document_headings") or []:
            lines.append("  - Observed heading: " + str(heading)[:130])
    lines.extend(["", "## Current implementation evidence"])
    for module, names in (audit.get("source_interfaces_inspected") or {}).items():
        lines.append("- `" + module + "`: " + ", ".join(names[:9]))
    lines.extend([
        "",
        "## Evidence-first upgrade hypotheses — not approved",
    ])
    for item in value.get("upgrade_hypotheses") or []:
        lines.append("- " + str(item))
    lines.extend(["", "## Verification questions"])
    for q in value.get("comparison_questions") or []:
        lines.append("- " + q)
    lines.extend([
        "",
        "**Next:** compare the inspected original documents with actual code paths,"
        " negative tests and current runtime before making a scoped patch.",
        "No commercial action or production completion is implied.",
        "",
    ])
    return "\n".join(lines)


def research_once(
    root: Path,
    *,
    search_fn: Callable[..., Mapping[str, Any]] = search_resilient,
    now: datetime | None = None,
    force: bool = False,
    max_queries: int = 1,
    interval_minutes: int = 30,
    source_inspector: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute bounded research using the existing ASTRA timer, not a daemon.

    Every source is unverified until original-page review; every change is
    a proposal, not an auto-approved implementation.
    """
    root = root.resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("research time must include an offset")
    now = now.astimezone(timezone.utc)
    state_file = root / OUTPUT / "state.json"
    state = load(state_file)
    last = timestamp(state.get("last_search_at"))
    if not force and last and now - last < timedelta(minutes=max(1, interval_minutes)):
        return {
            "status": "COOLDOWN", "searches_executed": 0,
            "next_at": (last + timedelta(minutes=max(1, interval_minutes))).isoformat(),
            "execution_authority": "none",
        }
    registry = build_completion_capability_registry(root)
    rows = sorted(registry["workstreams"], key=lambda row: (
        PRIORITY.index(row["key"]) if row["key"] in PRIORITY else len(PRIORITY),
        row["key"],
    ))
    entries = state.get("entries")
    entries = entries if isinstance(entries, dict) else {}
    actions = []
    for _ in range(max(1, min(int(max_queries), 3))):
        selected = None
        for row in rows:
            key = row["key"]
            record = entries.get(key)
            record = record if isinstance(record, dict) else {}
            old_phases = record.get("phases")
            phases = dict(old_phases) if isinstance(old_phases, dict) else {}
            digest = fingerprint(row)
            if record.get("fingerprint") != digest:
                phases = {}
            if len(phases) >= len(PHASES) and all(
                not phases[p].get("retry_required") for p in PHASES
            ):
                completed = timestamp(record.get("completed_at"))
                if completed and now - completed < timedelta(days=7):
                    continue
                phases = {}
            phase = next((p for p in PHASES if (
                p not in phases or phases[p].get("retry_required") is True
            )), None)
            if phase:
                selected = row, digest, phases, phase
                break
        if selected is None:
            break
        row, digest, phases, phase = selected
        # Backfill original-source inspection for research collected before
        # primary-page inspection was introduced, once per old phase.
        previous_inspector = source_inspector
        if previous_inspector is None and search_fn is search_resilient:
            previous_inspector = inspect_primary_page
        if previous_inspector is not None:
            for earlier in PHASES:
                old_phase = phases.get(earlier)
                if not isinstance(old_phase, dict):
                    continue
                if (old_phase.get("source_pages_independently_checked")
                        or old_phase.get("source_seed_review_attempted")):
                    continue
                checked = False
                for source in old_phase.get("sources") or []:
                    if not any(
                        source["domain"] == d or source["domain"].endswith("." + d)
                        for d in OFFICIAL_DOCUMENT_DOMAINS
                    ):
                        continue
                    try:
                        review = previous_inspector(source["url"])
                    except Exception as error:
                        review = {"status": "DOCUMENT_ACCESS_UNAVAILABLE",
                                  "error_type": type(error).__name__}
                    source["page_inspection"] = dict(review)
                    source["retrieved_page_verified"] = (
                        review.get("status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
                    )
                    checked = checked or source["retrieved_page_verified"]
                    if checked:
                        break
                if not checked:
                    primary = citation(official_seed(row, earlier))
                    if primary and primary["url"] not in {
                        s["url"] for s in old_phase.get("sources") or []
                    }:
                        try:
                            outcome = previous_inspector(primary["url"])
                        except Exception as error:
                            outcome = {"status": "DOCUMENT_ACCESS_UNAVAILABLE",
                                       "error_type": type(error).__name__}
                        primary["page_inspection"] = dict(outcome)
                        primary["retrieved_page_verified"] = (
                            outcome.get("status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
                        )
                        primary["discovery_origin"] = "CURATED_PRIMARY_STANDARD"
                        if primary["retrieved_page_verified"]:
                            old_phase.setdefault("sources", []).append(primary)
                            checked = True
                old_phase["source_review_attempted"] = True
                old_phase["source_seed_review_attempted"] = True
                old_phase["source_pages_independently_checked"] = checked
                break
        query = query_for(row, phase)
        try:
            response = search_fn(query, num=SEARCH_RESULTS_LIMIT)
            if not isinstance(response, Mapping):
                response = {}
        except Exception as error:
            response = {"error_type": type(error).__name__}
        sources = []
        seen = set()
        raw = response.get("organic") or []
        if isinstance(raw, list):
            for item in raw[:SEARCH_RESULTS_LIMIT]:
                c = citation(item) if isinstance(item, Mapping) else None
                if c is not None and c["url"] not in seen:
                    seen.add(c["url"])
                    sources.append(c)
        inspector = source_inspector
        if inspector is None and search_fn is search_resilient:
            inspector = inspect_primary_page
        if inspector is not None:
            # Read only one accepted primary page per phase, never arbitrary URLs.
            for source in sources:
                if not any(
                    source["domain"] == domain or
                    source["domain"].endswith("." + domain)
                    for domain in OFFICIAL_DOCUMENT_DOMAINS
                ):
                    continue
                try:
                    checked = inspector(source["url"])
                except Exception as error:
                    checked = {"status": "DOCUMENT_ACCESS_UNAVAILABLE",
                               "error_type": type(error).__name__}
                source["page_inspection"] = dict(checked)
                source["retrieved_page_verified"] = (
                    checked.get("status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
                )
                if source["retrieved_page_verified"]:
                    break
            if not any(s.get("retrieved_page_verified") for s in sources):
                # Search discovery can be degraded. Inspect a *known original*
                # standards document directly, and label its distinct origin.
                seed = citation(official_seed(row, phase))
                if seed and seed["url"] not in seen:
                    try:
                        reviewed = inspector(seed["url"])
                    except Exception as error:
                        reviewed = {"status": "DOCUMENT_ACCESS_UNAVAILABLE",
                                    "error_type": type(error).__name__}
                    seed["page_inspection"] = dict(reviewed)
                    seed["retrieved_page_verified"] = (
                        reviewed.get("status") == "ORIGINAL_HTML_HEADINGS_INSPECTED"
                    )
                    seed["discovery_origin"] = "CURATED_PRIMARY_STANDARD"
                    if seed["retrieved_page_verified"]:
                        sources.append(seed)
        params = response.get("searchParameters") or {}
        params = params if isinstance(params, Mapping) else {}
        degraded = bool(response.get("error") or response.get("error_type")) or (
            params.get("search_state") == "PROVIDER_DEGRADED"
            or response.get("search_operational_status") == "DEGRADED"
        )
        previous_phase = phases.get(phase) or {}
        attempt = int(previous_phase.get("attempt_count") or 0) + 1
        attempted = {
            "query": query, "queried_at": now.isoformat(),
            "result_count": len(sources), "attempt_count": attempt,
            "provider_degraded": degraded,
            "sources": sources,
            "source_pages_independently_checked": any(
                source.get("retrieved_page_verified") is True for source in sources
            ),
        }
        if sources or attempt >= 3:
            phases[phase] = attempted
        else:
            # A degraded/empty search stays pending: this is an attempted
            # query, NOT completed deep research.
            phases[phase] = {**attempted, "retry_required": True}
        entries[row["key"]] = {
            "fingerprint": digest,
            "phases": phases,
            "completed_at": now.isoformat() if all(
                p in phases and not phases[p].get("retry_required") for p in PHASES
            ) else None,
        }
        review = dossier(row, entries[row["key"]], root)
        doc_folder = root / OUTPUT / "dossiers"
        save(doc_folder / (row["key"] + ".json"), review)
        md = doc_folder / (row["key"] + ".md")
        md_tmp = md.with_suffix(".md.tmp")
        md_tmp.write_text(review_markdown(review), encoding="utf-8")
        md_tmp.replace(md)
        actions.append({
            "workstream": row["key"],
            "research_phase": phase,
            "sources_found": len(sources),
            "status": review["status"],
            "provider_degraded": degraded,
        })
        # Persist immediately: a later search timeout must not destroy progress.
        save(state_file, {
            "schema": "empire.system_research_state.v1",
            "last_search_at": now.isoformat(),
            "entries": entries, "workstream_count": len(rows),
            "execution_authority": "none",
        })
    payload = {
        "schema": "empire.system_improvement_research_agent.v1",
        "observed_at": now.isoformat(),
        "status": "RESEARCHED" if actions else "RESEARCH_CYCLE_CURRENT",
        "workstreams_total": len(rows),
        "research_steps": actions,
        "searches_executed": len(actions),
        "workstreams_started": sum(bool(x.get("phases")) for x in entries.values()),
        "workstreams_three_phases": sum(
            all(p in (x.get("phases") or {}) and not (x.get("phases") or {})[p].get("retry_required")
                for p in PHASES) for x in entries.values()
        ),
        "next_stage": "SOURCE_PAGE_REVIEW_AND_LOCAL_PROOF_COMPARE",
        "implementation_authority": "none",
        "external_outreach": False,
        "payment_action": False,
        "auto_code_edits": False,
        "research_is_not_operational_completion": True,
        "mode": "OBSERVE",
    }
    coverage = []
    for spec in rows:
        entry = entries.get(spec["key"]) or {}
        attempts = entry.get("phases") or {}
        completed_phases = [
            p for p in PHASES
            if p in attempts and not attempts[p].get("retry_required")
        ]
        current_dossier = load(
            root / OUTPUT / "dossiers" / (spec["key"] + ".json")
        )
        coverage.append({
            "workstream": spec["key"],
            "owner": spec["owner"],
            "phases_completed": completed_phases,
            "research_status": current_dossier.get("status", "NOT_STARTED"),
            "production_completion": "NOT_ATTESTED_BY_RESEARCH",
        })
    save(root / OUTPUT / "coverage_latest.json", {
        "schema": "empire.system_improvement_research_coverage.v1",
        "generated_at": now.isoformat(),
        "workstream_count": len(rows),
        "research_complete_for_review": sum(
            x["research_status"] == "ORIGINAL_SOURCES_CHECKED_REVIEW_REQUIRED"
            for x in coverage
        ),
        "workstreams": coverage,
        "execution_authority": "none",
    })
    save(root / OUTPUT / "latest.json", payload)
    return payload
