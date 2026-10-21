"""Research-to-review bridge for EmpireOS; never an executable work queue.

Each dossier or unresolved canonical claim becomes an idempotent proposal
with explicit source/test proof and human approval requirements. ASTRA only
writes these review artifacts, never enqueues them into DepartmentWorkQueue.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.system_improvement_research import OUTPUT as RESEARCH_DIR

OUTPUT = Path("runtime/system_improvement/review_packets")
MANIFEST = OUTPUT / "latest.json"
RESOLUTION = Path("runtime/opportunity_factory/evidence_resolution_latest.json")
SOURCE_CATALOG = {
    "conversation_os": (
        "runtime/conversations_replies_control/passive_reply_db_observer_latest.json",),
    "market_gps_and_commercial_outcomes": (
        "runtime/market_sweeps/revenue_gps_latest.json",
        "runtime/commercial_exchange/latest.json"),
    "buyer_capacity_readiness": (
        "runtime/buyer_capacity_readiness/latest.json",),
    "commercial_product_catalog": (),
    "commercial_product_catalog_and_fulfilment": (),
    "sensor_mesh": (),
    "search_fabric_and_sensor_mesh": (
        "runtime/opportunity_radar/research_latest.json",),
    "intelligence_fabric": (),
    "empire_coder": (),
}
CRITICAL_CLAIMS = {"buyer_intent", "demand", "fulfilment_readiness", "urgency"}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_if_changed(path: Path, value: Mapping[str, Any]) -> bool:
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == encoded:
        return False
    if path.is_file() and path.parent.name == "pending":
        existing = _read(path)
        if (
            existing.get("state") != "REVIEW_PENDING"
            or existing.get("approved_for_implementation") is not False
            or existing.get("auto_dispatch_eligible") is not False
        ):
            raise ValueError("review packet has external state; reconcile manually")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(encoded, encoding="utf-8")
    temp.replace(path)
    return True


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _proof_source(root: Path, relative: str, now: datetime) -> dict[str, Any]:
    path = root / relative
    info = {"relative_path": relative, "artifact_present": path.is_file(),
            "canonical_business_proof_verified": False}
    if not path.is_file():
        return info
    data = _read(path)
    timestamp = data.get("generated_at") or data.get("observed_at")
    info["reported_at"] = timestamp
    info["source_schema"] = data.get("schema_version") or data.get("schema")
    info["source_reported_status"] = str(data.get("status") or "")[:60]
    info["source_is_authenticated_event_stream"] = False
    try:
        event = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if event.tzinfo is not None:
            info["age_days"] = round(
                (now - event.astimezone(timezone.utc)).total_seconds() / 86400, 2
            )
            info["freshness"] = (
                "FUTURE_TIMESTAMP" if info["age_days"] < -0.01
                else "STALE_OVER_7_DAYS" if info["age_days"] > 7
                else "OBSERVED_WITHIN_7_DAYS"
            )
        else:
            info["freshness"] = "UNPROVEN"
    except (ValueError, TypeError):
        info["freshness"] = "UNPROVEN"
    return info


def _common(id_key: str, kind: str, owner: str) -> dict[str, Any]:
    return {
        "task_id": "improve_" + _digest([kind, id_key])[:18],
        "task_type": kind, "owner": owner,
        "state": "REVIEW_PENDING",
        "execution_queue": "ISOLATED_REVIEW_ONLY",
        "approved_for_implementation": False,
        "auto_dispatch_eligible": False,
        "write_to_department_work_queue": False,
        "allow_outbound": False,
        "allow_payment": False,
        "allow_db_migration": False,
        "execution_authority": "none",
    }

def build_review_packets(
    root: Path, *,
    resolution: Mapping[str, Any],
    dossiers: Mapping[str, Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build exact review packets from observed sources, not model assertions."""
    root = root.resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    now = now.astimezone(timezone.utc)
    if (resolution.get("execution_authority") != "none"
            or resolution.get("normalized_scores_written") != 0
            or resolution.get("factory_promotion_authorized") is not False):
        raise ValueError("unsafe or unverifiable source resolution")
    packets: list[dict[str, Any]] = []
    counts: dict[str, set[str]] = defaultdict(set)
    missing_tenant: dict[str, set[str]] = defaultdict(set)
    diagnostics: dict[str, set[str]] = defaultdict(set)
    examples: dict[str, dict[str, Any]] = {}
    for opportunity in resolution.get("items") or []:
        if not isinstance(opportunity, Mapping):
            continue
        key = opportunity.get("opportunity_key")
        for req in opportunity.get("requirements") or []:
            if not isinstance(req, Mapping) or not req.get("claim_type"):
                continue
            if req.get("verified_normalized_score") is not None:
                raise ValueError("resolver tried to promote a score")
            claim = str(req["claim_type"])
            source = str(req.get("source_capability") or "SOURCE_NOT_ROUTED")
            group = claim + "|" + source
            if key:
                counts[group].add(str(key))
                if req.get("tenant_binding_status") == "MISSING_TENANT_SCOPE":
                    missing_tenant[group].add(str(key))
            diag = req.get("source_diagnostic") or {}
            if isinstance(diag, Mapping):
                diagnostics[group].update(str(v) for v in (diag.get("reasons") or [])
                                          if isinstance(v, str) and len(v) <= 90)
            examples[group] = dict(req)

    for group, keys in sorted(counts.items()):
        claim, source = group.split("|", 1)
        ref = examples[group]
        source_candidates = SOURCE_CATALOG.get(source, ())
        probes = [_proof_source(root, name, now) for name in source_candidates]
        item = {
            **_common(group, "CLAIM_SOURCE_INTEGRATION", "data_quant"),
            "claim_type": claim,
            "target_capability": source,
            "affected_opportunity_count": len(keys),
            "opportunities_without_tenant_scope": len(missing_tenant[group]),
            "source_health_reason_codes": sorted(diagnostics[group]),
            "source_remediation": list((
                (resolution.get("commercial_source_health") or {}).get("sources") or {}
            ).get(source, {}).get("next_remediation") or [])[:4],
            "current_reason": ref.get("evidence_state"),
            "admissible_source_types": ref.get("allowed_source_kinds") or [],
            "existing_source_observers": probes,
            "source_connector_mapping": (
                "CANDIDATE_READ_ONLY_SNAPSHOT" if probes
                else "UNMAPPED_IN_SHADOW_REVIEW_BRIDGE"
            ),
            "root_cause_status": "NOT_YET_INDEPENDENTLY_VERIFIED",
            "hypothesis": (
                "Link original verified, identity-bound and tenant-safe events "
                "from the named capability to the existing Evidence Resolver"
            ),
            "verification_contract": {
                "source_identity": "independently authenticate original canonical event",
                "binding": "exact opportunity + tenant + product/claim when applicable",
                "privacy": "consent, suppression, data rights, provenance",
                "freshness": "event timestamps and claim-specific expiry",
                "negative_tests": [
                    "cross_tenant", "stale_event", "mismatched_entity",
                    "untrusted_source", "spoofed_verification",
                ],
                "business_outcome": (
                    "genuine buyer and fulfilment outcome proof; not more search hits"
                ),
            },
            "references": [
                str(RESOLUTION),
                "claim:" + claim + "|capability:" + source,
            ],
            "priority": "P0" if claim in CRITICAL_CLAIMS else "P1",
            "founder_gate_required_before_consequential_action": True,
        }
        packets.append(item)

    for key, doc in sorted(dossiers.items()):
        if doc.get("execution_authority") != "none":
            continue
        if doc.get("status") != "ORIGINAL_SOURCES_CHECKED_REVIEW_REQUIRED":
            continue
        audit = doc.get("audit") or {}
        evidence = [
            str(x.get("url"))
            for x in (doc.get("citations_to_inspect") or [])
            if x.get("retrieved_page_verified") is True and x.get("url")
        ]
        if len({x.split("/")[2] for x in evidence}) < 2:
            continue
        workstream = str(key)
        item = {
            **_common(workstream, "SOURCE_BACKED_ENGINEERING_REVIEW",
                      str(audit.get("owner") or "engineering")),
            "workstream": workstream,
            "source_review_status": doc["status"],
            "inspected_primary_source_urls": evidence[:8],
            "local_source_modules": list(audit.get("module_examples") or [])[:12],
            "related_test_files_discovered": list(
                audit.get("related_tests_discovered") or []
            )[:16],
            "local_test_execution_proved_by_research": False,
            "pending_checklist_count": int(audit.get("checklist_pending") or 0),
            "upgrade_hypotheses": list(doc.get("upgrade_hypotheses") or [])[:5],
            "root_cause_status": "NOT_YET_INDEPENDENTLY_VERIFIED",
            "verification_contract": {
                "audit": "inspect actual entrypoint + dependencies + DB + timers",
                "design": "compare exact source documents to current module behavior",
                "tests": "targeted unit, negative, integration, full regression",
                "production": "run reviewed bounded activation then verify artifacts",
                "business": "measure downstream real outcomes, not file existence",
                "approval": "founder or delegated approved engineering gate",
            },
            "references": [
                str(RESEARCH_DIR / "dossiers" / (workstream + ".json")),
                str(RESEARCH_DIR / "dossiers" / (workstream + ".md")),
            ],
            "priority": "P0" if workstream == "opportunity_factory" else "P1",
            "founder_gate_required_before_consequential_action": True,
        }
        packets.append(item)
    return {
        "schema": "empire.system_improvement_review_plan.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "task_count": len(packets),
        "claim_source_task_count": sum(
            x["task_type"] == "CLAIM_SOURCE_INTEGRATION" for x in packets
        ),
        "source_backed_engineering_review_count": sum(
            x["task_type"] == "SOURCE_BACKED_ENGINEERING_REVIEW"
            for x in packets
        ),
        "review_packets": packets,
        "automatic_execution_authority": "none",
        "approval_gates_preserved": True,
        "scores_written": 0,
        "live_outbound_sent": False,
        "department_work_queue_mutated": False,
    }

def verify_review_source_freshness(kind: str, source: Mapping[str, Any],
                                   *, now: datetime,
                                   max_age_seconds: int = 3600) -> dict[str, Any]:
    """Check snapshot-clock freshness without claiming source authenticity.

    This is an existing-review-layer check, not a change to the digest-pinned
    Harness² guard implementation or its recorded evaluation evidence.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware review clock required")
    if type(max_age_seconds) is not int or not 0 < max_age_seconds <= 86400:
        raise ValueError("invalid bounded observation freshness window")
    timestamp_field = {
        "conversion": "observed_at",
        "acquisition": "generated_at",
        "revenue": "generated_at",
    }.get(kind)
    if timestamp_field is None:
        raise ValueError("unknown original source freshness contract")
    raw=source.get(timestamp_field)
    if not isinstance(raw,str) or len(raw)>48:
        raise ValueError("source observation timestamp missing")
    try:
        timestamp=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError as error:
        raise ValueError("source observation timestamp invalid") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("source timestamp must be timezone-aware")
    age=(now.astimezone(timezone.utc)-timestamp.astimezone(timezone.utc)).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ValueError("source observation stale or future-dated")
    return {
        "source_clock":timestamp.astimezone(timezone.utc).isoformat(),
        "source_age_seconds":round(age,3),
        "fresh_at_review":True,
        "source_authenticity_independently_verified":False,
        "execution_authority":"none",
    }


def refresh_review_packets(root: Path) -> dict[str, Any]:
    """Materialize isolated review packets, never runnable department jobs."""
    root = root.resolve()
    resolution = _read(root / RESOLUTION)
    if not resolution:
        return {
            "status": "BLOCKED_MISSING_EVIDENCE_RESOLUTION",
            "task_count": 0, "execution_authority": "none",
        }
    folder = root / RESEARCH_DIR / "dossiers"
    dossiers = {}
    for path in sorted(folder.glob("*.json")):
        if not path.stem.isidentifier():
            continue
        candidate = _read(path)
        if candidate.get("workstream") == path.stem:
            dossiers[path.stem] = candidate
    output = build_review_packets(root, resolution=resolution, dossiers=dossiers)
    # Only admit the bounded, source-linked Harness²/SkillForge review into
    # this existing non-executable queue. Real sales observations are checked
    # with the trusted guard, and a pinned candidate is still never approved.
    # This is not a forecast, payment, buyer reply or Department completion.
    from empire_os.astra_review_queue_bridge import merge_into_review_plan
    from empire_os.astra_harness_evidence_guard import verified_snapshot_facts
    from empire_os.skillforge_harness2_bridge import skillforge_harness2_candidate
    import json as _harness_json
    observed_inputs = {
        "conversion": "runtime/conversion/latest.json",
        "acquisition": "runtime/buyer_acquisition/latest.json",
        "revenue": "runtime/revenue_pulse/latest.json",
    }
    valid_sources = True
    for _kind, _relative in observed_inputs.items():
        _source = root / _relative
        if (_source.is_symlink() or not _source.is_file() or
                not 0 < _source.stat().st_size <= 2_000_000):
            valid_sources = False
            break
        try:
            _payload = _harness_json.loads(_source.read_text(encoding="utf-8"))
            verified_snapshot_facts(_kind, _payload)
            verify_review_source_freshness(_kind, _payload, now=datetime.now(timezone.utc))
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            valid_sources = False
            break
    if valid_sources:
        _candidate = skillforge_harness2_candidate(root)
        _review = {
            "schema_version": "empire.astra.unified_intelligence_review.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "campaign_activation_authorized": False,
            "outbound_authorized": False,
            "owner_actions": [],
            "harness2_skillforge_candidate": _candidate,
        }
        output = merge_into_review_plan(output, _review)
    # Reuse the existing isolated engineering review queue for original-source
    # independence gaps in the *existing* SkillForge observations. This never
    # promotes a skill, dispatches a task or changes source data. A broken
    # SkillForge source audit cannot block unrelated review packets.
    from empire_os.skillforge_independent_evidence import review_independent_skill_evidence
    from empire_os.skillforge_coder_replay_review import (
        read_pinned_coder_replay, read_pinned_coder_patch_provenance,
    )
    from empire_os.astra_review_queue_bridge import merge_skillforge_evidence_into_review_plan
    try:
        _diversity=review_independent_skill_evidence(root)
        if _diversity["status"]=="SOURCE_DIVERSITY_REVIEW_ONLY":
            _diversity["coder_current_revision_replay"]=read_pinned_coder_replay(root)
            _diversity["coder_original_patch_provenance"]=read_pinned_coder_patch_provenance(root)
            output=merge_skillforge_evidence_into_review_plan(output,_diversity)
    except (OSError,ValueError,TypeError,UnicodeError):
        pass
    modified = 0
    unchanged = 0
    pointers = []
    for item in output["review_packets"]:
        pid = item["task_id"]
        dst = root / OUTPUT / "pending" / (pid + ".json")
        changed = _write_if_changed(dst, item)
        modified += int(changed)
        unchanged += int(not changed)
        pointers.append({
            "task_id": pid, "type": item["task_type"],
            "priority": item["priority"],
            "owner": item["owner"],
            "path": str(dst.relative_to(root)),
            "state": "REVIEW_PENDING",
        })
    # Manifest contains no executable queue identifier or approval token.
    summary = {
        "schema": output["schema"],
        "generated_at": output["generated_at"],
        "status": "REVIEW_PACKETS_READY",
        "task_count": output["task_count"],
        "claim_source_task_count": output["claim_source_task_count"],
        "source_backed_engineering_review_count": (
            output["source_backed_engineering_review_count"]
        ),
        "new_or_changed_review_packets": modified,
        "unchanged_review_packets": unchanged,
        "packets": pointers,
        "review_only": True,
        "auto_dispatch_eligible": False,
        "department_work_queue_mutated": False,
        "automatic_execution_authority": "none",
        "outbound_or_payment_authority": "none",
    }
    _write_if_changed(root / MANIFEST, summary)
    md_path = root / OUTPUT / "latest.md"
    md_text = review_board(output)
    if not md_path.exists() or md_path.read_text(encoding="utf-8") != md_text:
        md_temp = md_path.with_suffix(".md.tmp")
        md_temp.write_text(md_text, encoding="utf-8")
        md_temp.replace(md_path)
    return summary

def review_board(plan: Mapping[str, Any]) -> str:
    """Produce a P0-first review board without exposing prospect identifiers."""
    items = list(plan.get("review_packets") or [])
    items.sort(key=lambda p: (
        0 if p.get("priority") == "P0" else 1,
        p.get("task_type", ""), p.get("claim_type", p.get("workstream", "")),
    ))
    lines = [
        "# EmpireOS Evidence & Research Improvement Board",
        "",
        "All items require explicit engineering/founder review. "
        "Nothing here is eligible for automatic execution.",
        "",
        f"Review tasks: **{len(items)}**. "
        f"Claim/source groups: **{plan.get('claim_source_task_count', 0)}**. "
        f"Source-backed engineering reviews: "
        f"**{plan.get('source_backed_engineering_review_count', 0)}**.",
        "",
        "| Priority | Claim/workstream | Owner capability | Affected opportunities | Tenant-unscoped | Proof-source status |",
        "|---|---|---|---:|---:|---|",
    ]
    for item in items:
        claim = item.get("claim_type") or item.get("workstream") or "unknown"
        capability = item.get("target_capability") or item.get("owner")
        source_status = item.get("source_connector_mapping") or (
            "ORIGINAL_SOURCES_INSPECTED__REVIEW_REQUIRED"
        )
        lines.append(
            f"| {item['priority']} | {claim} | {capability} | "
            f"{item.get('affected_opportunity_count', 0)} | "
            f"{item.get('opportunities_without_tenant_scope', 0)} | {source_status} |"
        )
    lines.extend([
        "",
        "## Evidence-source observations",
        "",
        "Observer presence is not authenticated commercial proof; source identity, "
        "tenant binding and genuine business outcomes must be verified.",
        "",
    ])
    for item in items:
        if item.get("task_type") != "CLAIM_SOURCE_INTEGRATION":
            continue
        source_info = item.get("existing_source_observers") or []
        label = str(item.get("claim_type")) + " / " + str(item.get("target_capability"))
        blockers = item.get("source_health_reason_codes") or []
        if blockers:
            lines.append(f"- **{label} — blockers:** " + ", ".join(str(v) for v in blockers[:8]))
        actions = item.get("source_remediation") or []
        for action in actions[:3]:
            lines.append(f"  - Proposed governed repair: {action.get('action', 'review_original_source')} (not executed)")
        if not source_info:
            lines.append(f"- **{label}**: source observer not yet mapped in this review bridge; upstream source existence unverified")
            continue
        for source in source_info:
            lines.append(
                f"- **{label}**: `{source['relative_path']}`, "
                f"present={source['artifact_present']}, "
                f"freshness={source.get('freshness', 'UNKNOWN')}. "
                "This is *not* authenticated commercial proof."
            )
    lines.extend([
        "",
        "## Release requirements",
        "",
        "A packet can leave review only after its exact source, tenant and entity "
        "bindings, authenticity, freshness, negative tests, and end-to-end "
        "production/business outcome are independently demonstrated.",
        "",
        "The existing Opportunity Factory acceptance thresholds, founder gates, "
        "outbound suppression, money movement, tenant authority and execution "
        "queue remain unchanged.",
        "",
    ])
    return "\n".join(lines)
