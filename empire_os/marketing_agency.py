"""Marketing Director's deterministic OBSERVE orchestration, without executors."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile

from empire_os import copywriter, media_content_pipeline, traffic_specialist
from empire_os.predictive_revenue_formula import next_best_action_value
from empire_os.search_intelligence.attribution import preview_search_revenue_attribution
from empire_os.revenue_distribution import SOURCES, build_revenue_distribution

ROLES = {
    "marketing_director": ("marketing_agency",),
    "market_intelligence_strategist": ("opportunity_radar", "search_intelligence", "search_fabric", "competitive_intelligence"),
    "traffic_specialist": ("traffic_specialist",),
    "content_copy_agent": ("copywriter", "marketing", "agi_marketing"),
    "creative_media_agent": ("media_content_pipeline", "media_repurposing", "media_refresh"),
    "distribution_agent": ("media_empire_bridge", "media_research_bridge", "traffic_specialist"),
    "conversion_specialist": ("conversion_intelligence", "conversion_data_repository", "conversion_runtime"),
    "lifecycle_crm_agent": ("revenue_crm_search_growth", "conversation_value"),
    "attribution_agent": ("search_intelligence.attribution", "commercial_funnel"),
    "brand_quality_agent": ("media_claim_verification", "media_repurposing"),
    "paid_acquisition_planner": (),
}
AUTHORITY = dict.fromkeys(("external_publish", "auto_indexation", "live_outbound", "paid_traffic", "publishing", "indexation", "outbound", "binding_terms", "payment", "revenue_recognition"), False)
STAGES = "OBSERVE INTAKE RESEARCH STRATEGY SPECIALIST_ASSIGNMENT PRODUCTION_PLAN QUALITY_REVIEW CONVERSION_PLAN ATTRIBUTION_PLAN PREDICTIVE_REVENUE_REVIEW NEXT_BEST_ACTION RECORD".split()
ATTRIBUTION_CHAIN = "asset visitor conversion prospect conversation terms payment fulfilment recognized_revenue".split()
OUTPUT = Path("runtime/astra/department_cycle_latest.json")


def _action(kind, job_id, refs, **extra):
    return {"action_type": kind, "agency_job_id": job_id, "evidence_refs": refs,
            "classification": "PROPOSAL", "zero_cash_mode": True,
            "paid_media_spend_cents": 0, "total_action_cost_cents": None,
            "execution_authority": "none", **extra}


def build_marketing_agency(snapshots, *, generated_at, limit=5):
    """Reuse source validation, formula, search and conversion evidence adapters."""
    if not 0 <= limit <= 5:
        raise ValueError("agency intake limit must be between zero and five")
    distribution = build_revenue_distribution(snapshots, generated_at=generated_at)
    radar = snapshots.get("radar") or {}
    catalog = snapshots.get("catalog") or {}
    radar_rows = radar.get("candidates", []) if isinstance(radar, dict) else []
    catalog_rows = catalog.get("products", []) if isinstance(catalog, dict) else []
    radar_rows = radar_rows if isinstance(radar_rows, list) else []
    catalog_rows = catalog_rows if isinstance(catalog_rows, list) else []
    raw = {r.get("opportunity_key"): r for r in radar_rows if isinstance(r, dict)}
    products = {r.get("product_code"): r for r in catalog_rows if isinstance(r, dict)}
    candidates, rejected = [], []
    organic_keys = {a.get("opportunity_key") for a in distribution["organic_growth"]["traffic_specialist"]["actions"]}
    for opportunity in distribution["opportunities"]:
        key = opportunity["opportunity_key"]
        if key not in organic_keys:
            continue
        row = raw[key]
        if any(row.get(k) for k in ("tenant_id", "account_id", "customer_id")):
            rejected.append({"opportunity_key": key, "reason": "tenant_authorized_intake_required"})
            continue
        matches = [p for p in opportunity["product_matches"] if p["product_id"] and p["evidence_refs"]]
        if not matches:
            # Explicit product ambiguity fails closed; absent product is research-only.
            if row.get("products") or row.get("offer_key"):
                rejected.append({"opportunity_key": key, "reason": "explicit_catalog_product_required"})
                continue
            matches = [{"product_id": None, "product_code": None, "evidence_refs": [],
                        "binding_terms_ready": False, "readiness_blockers": ["product_fit_unknown"]}]
        for product in matches:
            catalog_product = products.get(product["product_code"], {})
            if any(catalog_product.get(k) for k in ("tenant_id", "account_id", "customer_id")):
                rejected.append({"opportunity_key": key, "reason": "tenant_scoped_catalog_product"})
                continue
            ready = product["binding_terms_ready"] is True
            conversation = bool(row.get("conversation_id") and row.get("conversation_evidence_refs"))
            priority = 1 if conversation else 2 if ready else 3
            candidates.append((priority, key, product["product_code"], opportunity, row, product))
    # Distribution already owns canonical order; retain it, including unknown economics.
    jobs = []
    for priority, key, code, opportunity, row, matched in candidates[:limit]:
        product = products.get(code, {})
        refs = sorted(set(opportunity["evidence_refs"] + matched["evidence_refs"]))
        job_id = "agency_" + hashlib.sha256(f"{key}|{matched['product_id']}".encode()).hexdigest()[:24]
        prediction = opportunity["canonical_prediction"]
        audience = row.get("audience") or row.get("niche")
        content = _action("prepare_evidence_led_product_brief", job_id, refs,
                          asset_type="product_education_report", audience=audience,
                          draft=None, draft_status="UNAVAILABLE")
        # Draft wording remains an unapproved hypothesis. Do not promote Radar
        # observations into verified commercial claims for the copywriter.
        if audience and product.get("product_name"):
            draft = copywriter.build_copy(copywriter.CopyBrief(
                channel="landing_hero", objective="product education",
                product_code=code, product_name=product["product_name"], audience=audience))
            content.update(draft=draft.as_dict(), draft_status="PROPOSAL_REQUIRES_CLAIM_REVIEW")
        traffic = traffic_specialist.review_organic_traffic([opportunity], {})["actions"]
        for action in traffic:
            action["agency_job_id"] = job_id
        creative = _action("prepare_video_image_chart_brief", job_id, refs,
                           prerequisite="verified_media_research_pack", asset_ref=None,
                           pipeline_owner="media_content_pipeline.build_content_pipeline")
        conversion = _action("review_landing_cta_and_funnel_friction", job_id, refs,
                             campaign_conversion_rate=None,
                             measurement="Measure observed visitor_to_lead and conversation transitions with denominators and time windows; do not substitute global rates.",
                             specialist_review=distribution["organic_growth"]["conversion_specialist"])
        attribution = _action("prepare_attribution_join_review", job_id, refs,
                              owner="search_intelligence.attribution.preview_search_revenue_attribution",
                              required_chain=ATTRIBUTION_CHAIN, source=None, medium=None,
                              observed_links={stage: None for stage in ATTRIBUTION_CHAIN},
                              revenue_linkage_status="UNAVAILABLE",
                              missing_evidence=ATTRIBUTION_CHAIN,
                              rule="Join observed first-party event identities to canonical commercial_events; only recognized actual revenue may be attributed.")
        next_action = _action("review_product_audience_and_source_evidence", job_id, refs)
        action_inputs = {"action_key": next_action["action_type"]}
        economic_evidence = row.get("action_economics") or {}
        economic_refs = row.get("action_economics_evidence_refs") or {}
        if isinstance(economic_evidence, dict) and isinstance(economic_refs, dict):
            for field in ("probability_action_changes_outcome", "incremental_revenue_if_changed_cents", "action_cost_cents", "confidence"):
                value = economic_evidence.get(field)
                links = economic_refs.get(field)
                if (isinstance(links, list) and any(isinstance(v, str) and v.strip() for v in links)
                        and type(value) in (int, float) and math.isfinite(value) and value >= 0
                        and (field not in {"confidence", "probability_action_changes_outcome"} or value <= 1)):
                    action_inputs[field] = value
        economics = next_best_action_value([action_inputs])
        economics["evidence_refs"] = economic_refs
        # Require a complete job-scoped identity chain before using the existing
        # attribution validator; partial joins must never imply revenue.
        observed = row.get("attribution_evidence")
        if isinstance(observed, dict) and observed.get("evidence_refs"):
            links = observed.get("links") or {}
            if (observed.get("opportunity_key") == key and observed.get("product_id") == matched["product_id"]
                    and all(links.get(stage) for stage in ATTRIBUTION_CHAIN)):
                try:
                    preview = preview_search_revenue_attribution(
                        site_id=observed.get("site_id"), commercial_event=observed.get("commercial_event"),
                        page_id=links["asset"], external_session_id=links["visitor"],
                        prospect_id=links["prospect"], opportunity_id=key)
                    event = observed["commercial_event"]
                    if event["id"] == links["recognized_revenue"] and event["fulfilment_order_id"] == links["fulfilment"]:
                        attribution.update(preview=preview.as_dict(), observed_links=links,
                                           revenue_linkage_status="AVAILABLE", missing_evidence=[],
                                           evidence_refs=observed["evidence_refs"])
                except (ValueError, TypeError, KeyError):
                    attribution["validation_status"] = "INVALID_EVIDENCE"
        missing = sorted(set(prediction.get("missing_fields", []) + [
            "verified_audience_fit", "current_timing_evidence", "campaign_conversion_events",
            "attribution_identity_chain", "verified_content_claims", "suppression_and_conversation_state",
            *matched["readiness_blockers"]]))
        jobs.append({
            "agency_job_id": job_id, "account_label": "Empire AI", "account_id": None, "tenant_id": None,
            "opportunity_key": key, "product_id": matched["product_id"], "product_code": code,
            "revenue_lane": row.get("revenue_lane"), "niche": row.get("niche"),
            "geography": row.get("geography") or row.get("metro"), "audience": audience,
            "audience_classification": "SOURCE_SEGMENT_REQUIRES_FIT_REVIEW",
            "objective": "Review evidenced product fit and prepare organic demand capture",
            "why_now": {"observed_trigger": row.get("trigger"), "current_urgency": None},
            "source_evidence_refs": refs, "market_evidence_refs": row.get("evidence_refs", []),
            "search_evidence_refs": distribution["search_intelligence"]["search"].get("evidence_refs", []),
            "competitive_evidence_refs": distribution["search_intelligence"]["competitor"].get("evidence_refs", []),
            "canonical_prediction": prediction, "predictive_revenue_status": prediction["status"],
            "predictive_revenue_missing_fields": prediction.get("missing_fields", []),
            "strategy": {"priority_tier": priority, "product_fit": "EXPLICIT_SOURCE_PRODUCT_REFERENCE",
                         "commercially_ready": matched["binding_terms_ready"], "positioning": "evidence_led_product_education"},
            "specialist_assignments": [{"role": role, "owners": list(owners), "coordinator": "marketing_director",
                                         "execution_authority": "none"} for role, owners in ROLES.items() if role != "marketing_director"],
            "traffic_plan": traffic, "content_plan": content, "creative_plan": creative,
            "distribution_plan": _action("review_owned_site_internal_links_and_organic_repurposing", job_id, refs,
                                          channels=["owned_site", "organic_search"], spam_allowed=False, fake_engagement_allowed=False),
            "conversion_plan": conversion, "attribution_plan": attribution,
            "cta_offer_path": {"proposal": "product education → voluntary enquiry → governed conversation", "product_code": code, "binding_offer": False},
            "lifecycle_plan": {"status": "BLOCKED_PENDING_CURRENT_STATE", "required_checks": ["suppression", "opt_out", "conversation_state", "outbound_authority"], "send_authorized": False},
            "quality_review": {"status": "HUMAN_REVIEW_REQUIRED", "publish_ready": False,
                               "required_checks": ["brand_consistency", "unsupported_claims", "duplicate_thin_content", "commercial_compliance"], "missing_evidence": missing},
            "next_best_action": {**next_action, "economics": economics},
            "economic_memory": {"write_performed": False, "required_evidence": "verified_commercial_outcome_before_outcome_conditioned_learning"},
            "mode": "OBSERVE", "classification": "PROPOSAL", "execution_authority": "none",
        })
    for job in jobs:
        _materialize_campaign(job, generated_at)
    counts = Counter(j["predictive_revenue_status"] for j in jobs)
    result = {
        "schema_version": "empire.marketing_agency.v1", "department_key": "marketing_growth",
        "operating_model": "ai_marketing_agency", "generated_at": generated_at,
        "mode": "OBSERVE", "execution_authority": "none", "authority": dict(AUTHORITY),
        "paid_acquisition_authorized": False, "paid_acquisition_plan": {"status": "DISABLED", "budget": None, "activation_authorized": False},
        "roles": {role: list(owners) for role, owners in ROLES.items()}, "cycle_stages": STAGES,
        "jobs": jobs, "agency_job_count": len(jobs), "active_campaign_plan_count": len(jobs),
        "campaign_plans": [{"agency_job_id": j["agency_job_id"], "status": "PROPOSAL", "strategy": j["strategy"]} for j in jobs],
        "predictive_revenue_available_count": counts["AVAILABLE"], "predictive_revenue_unavailable_count": counts["UNAVAILABLE"],
        "sources": distribution["sources"], "blockers": distribution["blockers"], "rejected_intake": rejected,
        "media_pipeline_review": {**media_content_pipeline.build_content_pipeline(None), "generated_at": generated_at},
        "media_pipeline_status": "VERIFIED_JOB_SCOPED_PACK_REQUIRED",
    }
    for kind in ("traffic", "content", "creative", "conversion", "attribution"):
        result[kind + "_actions"] = [a for j in jobs for a in (j[kind + "_plan"] if kind == "traffic" else [j[kind + "_plan"]])]
    result["zero_cash_action_count"] = sum(len(result[k + "_actions"]) for k in ("traffic", "content", "creative", "conversion", "attribution")) + len(jobs)
    result.update(
        campaigns=jobs, campaign_count=len(jobs), agency_roles=AGENCY_ROLES,
        campaign_state_counts=dict(Counter(j["current_stage"] for j in jobs)),
        traffic_action_count=sum(len(j["traffic_plan"]) for j in jobs),
        content_asset_count=sum(len(j["assets"]) for j in jobs),
        creative_brief_count=sum(len(j["creative_plan"]["briefs"]) for j in jobs),
        conversion_plan_count=len(jobs), attribution_plan_count=len(jobs),
        zero_cash_campaign_count=len(jobs), paid_traffic_authorized=False,
    )
    return result


def observe_marketing_agency(repo_root, *, generated_at=None):
    snapshots = {}
    for name, relative in SOURCES.items():
        try:
            snapshots[name] = json.loads((Path(repo_root) / relative).read_text())
        except (OSError, ValueError):
            snapshots[name] = None
    result = build_marketing_agency(snapshots, generated_at=generated_at or datetime.now(timezone.utc).isoformat())
    # Read the current distribution artifact, while revalidating its upstream inputs.
    path = Path(repo_root) / "runtime/revenue_distribution/latest.json"
    try:
        data = path.read_bytes()
        current = json.loads(data)
        result["distribution_input"] = {
            "path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
            "generated_at": current.get("generated_at"),
            "current_order": [r["opportunity_key"] for r in current.get("opportunities", [])],
            "eligibility": "revalidated_from_current_sources",
        }
    except (OSError, ValueError, TypeError, KeyError):
        result["distribution_input"] = {"status": "UNAVAILABLE", "eligibility": "revalidated_from_current_sources"}
    return result


def record_marketing_agency(repo_root):
    """Record only agency plans; never call the queue-processing cycle."""
    root = Path(repo_root)
    path = root / OUTPUT
    before = path.read_bytes() if path.exists() else None
    payload = json.loads(before) if before else {}
    agency = observe_marketing_agency(root)
    payload["marketing_growth"] = agency
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        if (path.read_bytes() if path.exists() else None) != before:
            raise RuntimeError("department snapshot changed concurrently; retry observe intake")
        temp.replace(path)
    finally:
        if temp and temp.exists():
            temp.unlink()
    return agency


AGENCY_ROLES = [
    "marketing_director", "market_intelligence", "traffic_specialist", "content_copy",
    "creative_media", "distribution", "conversion_specialist", "lifecycle_crm",
    "attribution_analytics", "brand_quality", "paid_acquisition_planner",
]
CAMPAIGN_STAGES = (
    "DISCOVERED", "INTAKE", "RESEARCHING", "STRATEGY_READY", "ASSET_BUILD",
    "QUALITY_REVIEW", "CONVERSION_READY", "READY_FOR_OWNED_ACTIVATION",
    "ACTIVE", "MEASURING", "OPTIMIZING", "PAUSED", "CLOSED",
)


def advance_campaign(campaign, target):
    """Only sequential internal transitions; no activation adapter in this slice."""
    current = campaign["current_stage"]
    if target not in CAMPAIGN_STAGES[:8]:
        raise ValueError("external activation requires a separate founder-approved slice")
    if CAMPAIGN_STAGES.index(target) != CAMPAIGN_STAGES.index(current) + 1:
        raise ValueError("campaign transition must be sequential")
    if target == "READY_FOR_OWNED_ACTIVATION" and not all(campaign["readiness_gates"].values()):
        raise ValueError("campaign readiness evidence missing")
    campaign["previous_stage"] = current
    campaign["current_stage"] = target
    campaign["stage_history"].append({"previous_stage": current, "stage": target,
                                      "evidence_refs": list(campaign["source_evidence_refs"])})


def _materialize_campaign(job, generated_at):
    """Run bounded draft production using existing specialist owners, without I/O."""
    refs = job["source_evidence_refs"]
    objective = "product_enquiry" if job["product_id"] else "research_enquiry"
    key = json.dumps([job["opportunity_key"], job["product_id"], objective], separators=(",", ":"))
    cid = "campaign_" + hashlib.sha256(key.encode()).hexdigest()[:24]
    job.update(campaign_id=cid, campaign_key=key, department_key="marketing_growth",
               operating_model="ai_marketing_agency", campaign_objective=objective,
               commercial_objective="Qualify voluntary interest before a governed commercial conversation",
               paid_media_spend_cents=0, total_campaign_cost_cents=None,
               current_stage="DISCOVERED", previous_stage=None,
               stage_history=[{"stage": "DISCOVERED", "previous_stage": None, "evidence_refs": list(refs)}],
               tenant_scope={"status": "INTERNAL_UNRESOLVED", "account_label": "Empire AI",
                             "tenant_id": None, "account_id": None, "customer_access_authorized": False,
                             "authorization_owner": "tenant_isolation.authorize_tenant_resource"},
               product_evidence_refs=[r for r in refs if "commercial_catalog" in r],
               opportunity_evidence_refs=list(refs), why_now_evidence_refs=list(refs))
    advance_campaign(job, "INTAKE")
    job["market_intelligence"] = {
        "target_audience": job["audience"], "geography": job["geography"],
        "market_context": "Source segment under research; not verified customer demand",
        "search_opportunity": "Review organic search coverage against source evidence",
        "competitive_gap": "Coverage evidence requires review" if job["opportunity_key"].startswith("competitor_coverage:") else None,
        "buyer_customer_problem": None, "why_now": job["why_now"],
        "product_fit": job["product_id"], "missing_evidence": ["validated_customer_problem", "search_demand", "audience_product_fit"],
        "evidence_refs": refs,
    }
    advance_campaign(job, "RESEARCHING")
    path = "/research/" + cid
    for action in job["traffic_plan"]:
        action.update(campaign_id=cid, owned_landing_path=path,
                      acquisition_route="organic_search → owned research page → voluntary enquiry",
                      production_steps=["Prepare research landing draft", "Review source provenance and audience relevance",
                                        "Propose contextual internal links from relevant owned pages",
                                        "After founder activation, measure organic landing sessions and enquiries"],
                      search_volume=None, expected_visitors=None, external_publish=False,
                      auto_indexation=False)
    job["distribution_plan"].update(owned_route=path, route_status="PROPOSED_NOT_DEPLOYED",
                                     activation_required=True, auto_indexation=False)
    advance_campaign(job, "STRATEGY_READY")
    assets = []
    audience = job["audience"]
    if audience and job["niche"] and job["geography"]:
        draft = copywriter.build_copy(copywriter.CopyBrief(
            channel="campaign_research", objective=objective,
            product_code=job["product_code"] or "UNKNOWN",
            product_name=job["product_code"] or "Research enquiry",
            audience=audience, niche=job["niche"], metro=job["geography"],
        )).as_dict()
        primary = media_content_pipeline.campaign_draft_content(
            content_id=cid + ":landing", topic=draft["headline"], audience=audience,
            body=draft["body"], cta=draft["cta"], evidence_refs=refs,
            opportunity_key=job["opportunity_key"], product_refs=job["product_evidence_refs"],
            generated_at=generated_at,
        )
        primary.update(asset_id=primary["content_id"], campaign_id=cid, asset_type="landing_page",
                       copy=draft, seo_title=draft["headline"],
                       meta_description=f"Review research questions for {job['niche']} in {job['geography']}. Explore evidence and its limits.",
                       h1=draft["headline"], h2=["Questions to investigate", "Evidence and limitations", "Discuss your requirements"],
                       sections=[{"heading": "Questions to investigate", "body": "Which sources describe this market? How recent are they? Do they establish customer need?"},
                                 {"heading": "Evidence and limitations", "body": "Source activity does not establish demand, product suitability or future revenue. Request source review before relying on any findings."}],
                       faq=[{"question": "Are results guaranteed?", "answer": "No. Traffic, conversion and revenue outcomes are unknown."},
                            {"question": "How should I evaluate the research?", "answer": "Review source provenance, dates, coverage and relevance to your requirements."}],
                       schema_recommendation="WebPage only after owned activation; no ratings, pricing or unsupported FAQ claims")
        assets.append(primary)
        for channel in ("linkedin", "facebook", "short_video"):
            body = (f"Research questions for {job['niche']} in {job['geography']}: "
                    "What do the sources show, what is missing, and what would validate customer need? "
                    f"{draft['cta']}. No performance forecast is implied.")
            assets.append({"asset_id": cid + ":" + channel, "campaign_id": cid,
                           "asset_type": channel, "body": body, "evidence_refs": list(refs),
                           "claims": [], "asset_status": "DRAFT", "publication_status": "NOT_PUBLISHED",
                           "public_publish_authorized": False, "execution_authority": "none"})
        job["content_plan"].update(draft=draft, draft_status="INTERNAL_DRAFT",
                                   asset_refs=[a["asset_id"] for a in assets])
    job["assets"] = assets
    job["asset_status"] = "DRAFT" if assets else "BLOCKED"
    job["creative_plan"]["briefs"] = [
        {"brief_id": cid + ":brief:" + kind, "kind": kind, "campaign_id": cid,
         "topic": f"{job['niche']} / {job['geography']}", "evidence_refs": list(refs),
         "treatment": treatment, "status": "PRODUCTION_BRIEF", "execution_authority": "none"}
        for kind, treatment in (
            ("hero_visual", "Typographic research title and geography. No fabricated business or customer imagery."),
            ("social_visual", "Square question card: What evidence would validate this market? Include research label."),
            ("video", "Open with the research question; show source provenance, then limitations; close with voluntary enquiry."),
            ("short_form_vertical_video", "Vertical three-scene edit: question, evidence checklist, enquiry CTA. Use campaign short_video script."),
            ("chart", "Evidence availability matrix, not market size. Rows: predictive factors. Cells: evidenced or unknown. No invented numeric axis."),
            ("thumbnail", "Research title on neutral background; no results, testimonials or customer logos."),
        )]
    job["creative_plan"].update(prerequisite="founder_activation_before_external_use",
                                asset_ref=assets[0]["asset_id"] if assets else None)
    advance_campaign(job, "ASSET_BUILD")
    # This limited template has no factual market claims. A substantive report
    # remains gated by media_claim_verification and verified research packs.
    claim_pass = bool(assets) and all(not a.get("claims") and a.get("evidence_refs") for a in assets)
    job["claim_review"] = {"status": "PASS" if claim_pass else "BLOCKED",
                           "scope": "claim-free research invitation templates",
                           "substantive_claims_owner": "media_claim_verification",
                           "evidence_refs": refs, "market_claims_verified": False}
    job["quality_review"].update(status="PASS_INTERNAL_DRAFT" if claim_pass else "BLOCKED",
                                  publish_ready=False, critical_blockers=[] if claim_pass else ["usable_asset_required"])
    advance_campaign(job, "QUALITY_REVIEW")
    cta = assets[0]["copy"]["cta"] if assets else None
    events = ["landing_view", "cta_click", "enquiry_submitted", "prospect_linked", "conversation_linked"]
    job["conversion_plan"].update(
        conversion_objective="product_enquiry" if job["product_id"] else "email_enquiry",
        primary_cta=cta, secondary_cta="Review evidence limitations", landing_path=path,
        required_fields=["reply_email", "research_question"], optional_fields=["company", "role"],
        proof_placement="Source provenance and limitations immediately before CTA",
        friction_review="No phone, budget or payment required; explain purpose of response data; no marketing consent inferred",
        measurement_events=events, endpoint_status="REQUIRES_ACTIVATION", experiment_winner=None,
    )
    job["attribution_plan"].update(
        campaign_id=cid, asset_ids=[a["asset_id"] for a in assets],
        source="owned_site", medium="organic", utm_campaign=cid,
        required_chain=["campaign_id", "asset_id", "source/channel", "visitor/session", "conversion_event",
                        "prospect", "conversation", "commercial_terms", "payment", "fulfilment", "recognized_revenue"],
        event_contract={"required": ["event_id", "campaign_id", "asset_id", "source", "channel", "occurred_at"],
                        "optional_observed_only": ["session_id", "prospect_id", "conversation_id", "commercial_event_id"],
                        "dedupe_key": "event_id", "identity_rule": "Never derive prospect identity from campaign or session"},
    )
    job["measurement_plan"] = {"events": events, "baseline_status": "UNAVAILABLE",
                               "visitors": None, "conversions": None, "conversion_rate": None,
                               "window": None, "attribution_owner": "search_intelligence.attribution",
                               "performance_evidence": [], "fresh_campaign_scoped_events_required": True}
    from empire_os.predictive_revenue_formula import CORE_FACTORS
    job["evidence_collection_plan"] = [
        {"factor": factor, "status": "MISSING" if factor in job["predictive_revenue_missing_fields"] else "EVIDENCED",
         "requirement": requirement, "campaign_id": cid, "mutation_authorized": False}
        for factor, requirement in zip((*CORE_FACTORS, "ltv_cents"), (
            "Observed relevant intent with denominator and time window", "Canonical prospect quality evidence",
            "Verified contact enrichment provenance", "Canonical Omega qualification evidence",
            "Verified buyer match and capacity", "Governed delivery evidence; no send authorized",
            "Fresh campaign conversions and denominators", "Canonical accepted commercial terms",
            "Verified payment event", "Verified fulfilment outcome", "Observed customer value over a defined window",
        ))]
    job["readiness_gates"] = {
        "real_opportunity_evidence": bool(refs), "defined_audience": bool(audience),
        "defined_owned_traffic_route": bool(job["traffic_plan"] and path),
        "usable_content_asset": bool(assets), "conversion_objective": bool(objective),
        "cta": bool(cta), "attribution_plan": bool(job["attribution_plan"].get("event_contract")),
        "claim_quality_review": claim_pass, "no_critical_blocker": not job["quality_review"]["critical_blockers"],
    }
    if all(job["readiness_gates"].values()):
        advance_campaign(job, "CONVERSION_READY")
        advance_campaign(job, "READY_FOR_OWNED_ACTIVATION")
    job["next_best_action"].update(action_type="request_founder_owned_activation" if job["current_stage"] == "READY_FOR_OWNED_ACTIVATION" else "resolve_readiness_blockers",
                                   prerequisites=["verified_owned_site", "tenant_account_resolution", "privacy_and_endpoint_review", "founder_activation"])
    job["optimization_loop"] = [
        {"step": step, "status": status, "evidence_refs": list(refs)}
        for step, status in (("OBSERVE", "COMPLETE"), ("ANALYSE", "COMPLETE"),
                             ("PROPOSE", "COMPLETE"), ("PRODUCE", "COMPLETE" if assets else "BLOCKED"),
                             ("QUALITY CHECK", job["claim_review"]["status"]),
                             ("MEASURE", "AWAITING_OBSERVATIONS"), ("COMPARE", "AWAITING_BASELINE"),
                             ("LEARN", "NO_OBSERVED_OUTCOME"), ("NEXT BEST ACTION", "PROPOSED"))]
