"""Live Predictive Revenue demo built from existing EmpireOS runtime truth.

This module is presentation/read-model code only. It does not generate synthetic
commercial evidence, mutate canonical state, execute outreach, create terms,
move funds, or recognize revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_revenue_private_deployment import (
    private_deployment_economics,
)


RUNTIME_SOURCES: dict[str, str] = {
    "revenue_os": "runtime/autonomous_revenue_os/latest.json",
    "predictive_cloud": "runtime/predictive_cloud/status_latest.json",
    "astra": "runtime/astra/executive_latest.json",
    "opportunity_loop": "runtime/opportunity_radar/loop_latest.json",
    "quant_review": "runtime/opportunity_factory/quant_review_latest.json",
    "opportunity_value": "runtime/opportunity_factory/value_latest.json",
    "buyer_acquisition": "runtime/buyer_acquisition/latest.json",
    "commercial_exchange": "runtime/commercial_exchange/latest.json",
    "revenue_exchange": "runtime/revenue_exchange/latest.json",
    "commercial_catalog": "runtime/commercial_catalog/latest.json",
    "revenue_pulse": "runtime/revenue_pulse/latest.json",
    "buyer_capacity": "runtime/buyer_capacity_readiness/latest.json",
    "enterprise_targets": "runtime/predictive_revenue/enterprise_targets_latest.json",
    "enterprise_pool": "runtime/predictive_revenue/enterprise_pool_latest.json",
    "enterprise_contacts": "runtime/predictive_revenue/enterprise_contact_intelligence_latest.json",
    "economic_memory": "runtime/economic_memory/latest.json",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _source_state(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    payloads: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}
    for key, relative in RUNTIME_SOURCES.items():
        path = root / relative
        payload = _read_json(path)
        payloads[key] = payload
        try:
            stat = path.stat()
            observed = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
            available = bool(payload)
        except OSError:
            observed = None
            available = False
        sources[key] = {
            "path": relative,
            "available": available,
            "file_observed_at": observed,
        }
    return payloads, sources


def _active_catalog_products(catalog: Mapping[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in catalog.get("products") or []:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("active") is not True or raw.get("binding_terms_ready") is not True:
            continue
        price = raw.get("price_basis")
        if not isinstance(price, Mapping):
            price = {}
        rows.append({
            "product_code": raw.get("product_code"),
            "product_name": raw.get("product_name"),
            "product_family": raw.get("product_family"),
            "billing_model": raw.get("billing_model"),
            "currency": raw.get("currency"),
            "amount_cents": price.get("amount_cents"),
            "unit": price.get("unit"),
            "price_state": price.get("state"),
            "actual_revenue": False,
        })
    rows.sort(
        key=lambda row: (
            -_int(row.get("amount_cents")),
            str(row.get("product_name") or ""),
        )
    )
    return rows[: max(1, int(limit))]


def _enterprise_targets(targets: Mapping[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in targets.get("targets") or []:
        if not isinstance(raw, Mapping):
            continue
        people = []
        for person in raw.get("observed_people") or []:
            if not isinstance(person, Mapping):
                continue
            people.append({
                "name": person.get("name"),
                "title": person.get("title"),
            })
        rows.append({
            "account_name": raw.get("account_name"),
            "account_type": raw.get("account_type"),
            "wave": raw.get("wave"),
            "target_product_codes": list(raw.get("target_product_codes") or []),
            "observed_scale": list(raw.get("observed_scale") or []),
            "observed_triggers": list(raw.get("observed_triggers") or []),
            "observed_people": people[:4],
            "fit_classification": raw.get("fit_classification"),
            "contact_verified": bool(raw.get("contact_verified")),
            "budget_verified": bool(raw.get("budget_verified")),
            "commercial_terms_verified": bool(raw.get("commercial_terms_verified")),
            "outreach_authorized": bool(raw.get("outreach_authorized")),
            "actual_revenue": False,
        })
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def build_predictive_revenue_demo(root: Path) -> dict[str, Any]:
    payloads, sources = _source_state(root)
    revenue_os = payloads["revenue_os"]
    cloud = payloads["predictive_cloud"]
    astra = payloads["astra"]
    loop = payloads["opportunity_loop"]
    quant = payloads["quant_review"]
    exchange = payloads["commercial_exchange"]
    revenue_exchange = payloads["revenue_exchange"]
    catalog = payloads["commercial_catalog"]
    pulse = payloads["revenue_pulse"]
    capacity = payloads["buyer_capacity"]
    buyer_team = payloads["buyer_acquisition"]
    enterprise_targets = payloads["enterprise_targets"]
    enterprise_pool = payloads["enterprise_pool"]
    enterprise_contacts = payloads["enterprise_contacts"]
    memory = payloads["economic_memory"]

    current_window = pulse.get("current_window")
    if not isinstance(current_window, Mapping):
        current_window = {}
    revenue_truth = pulse.get("recognized_revenue_truth")
    if not isinstance(revenue_truth, Mapping):
        revenue_truth = {}

    inventory = revenue_os.get("inventory")
    if not isinstance(inventory, Mapping):
        inventory = {}
    inventory_counts = inventory.get("counts")
    if not isinstance(inventory_counts, Mapping):
        inventory_counts = {}

    supply = exchange.get("supply_gate_diagnostics")
    if not isinstance(supply, Mapping):
        supply = {}

    private_economics = private_deployment_economics()

    cloud_available = _int(cloud.get("available_component_count"))
    cloud_total = _int(cloud.get("component_count"))
    actual_revenue_cents = _int(revenue_truth.get("recognized_revenue_cents"))

    astra_goals = []
    for goal in astra.get("goals") or []:
        if isinstance(goal, Mapping):
            astra_goals.append({
                "key": goal.get("key"),
                "priority": goal.get("priority"),
                "objective": goal.get("objective"),
                "reason": goal.get("reason"),
            })

    proof_chain = [
        {
            "stage": "OBSERVE",
            "label": "Real acquisition",
            "observed": _int(current_window.get("acquisitions")) > 0,
            "value": _int(current_window.get("acquisitions")),
            "evidence": "runtime/revenue_pulse/latest.json",
        },
        {
            "stage": "QUALIFY",
            "label": "Qualified in current 24h",
            "observed": _int(current_window.get("qualified")) > 0,
            "value": _int(current_window.get("qualified")),
            "evidence": "runtime/revenue_pulse/latest.json",
        },
        {
            "stage": "INVENTORY",
            "label": "Pre-qualified sellable inventory",
            "observed": _int(inventory_counts.get("PREQUALIFIED_LEAD")) > 0,
            "value": _int(inventory_counts.get("PREQUALIFIED_LEAD")),
            "evidence": "runtime/autonomous_revenue_os/latest.json",
        },
        {
            "stage": "BUYER MARKET",
            "label": "Buyer seats observed",
            "observed": _int(exchange.get("buyer_seat_count")) > 0,
            "value": _int(exchange.get("buyer_seat_count")),
            "evidence": "runtime/commercial_exchange/latest.json",
        },
        {
            "stage": "TERMS",
            "label": "Verified buyer terms",
            "observed": _int(capacity.get("terms_verified")) > 0,
            "value": _int(capacity.get("terms_verified")),
            "evidence": "runtime/buyer_capacity_readiness/latest.json",
        },
        {
            "stage": "REVENUE",
            "label": "Recognized revenue",
            "observed": actual_revenue_cents > 0,
            "value_cents": actual_revenue_cents,
            "evidence": "runtime/revenue_pulse/latest.json",
        },
    ]

    component_matrix = []
    for component_key, component in sorted(
        (cloud.get("components") or {}).items()
    ):
        if not isinstance(component, Mapping):
            continue
        component_matrix.append({
            "component": component_key,
            "available": bool(component.get("available")),
            "freshness": component.get("freshness"),
            "mode": component.get("mode"),
            "observed_at": component.get("observed_at"),
        })

    return {
        "schema_version": "empire.predictive-revenue.demo.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "LIVE_READ_ONLY",
        "living_proof": True,
        "title": "Empire AI Predictive Revenue — Live System Demo",
        "truth_contract": {
            "observed_is_separate_from_predicted": True,
            "predicted_is_not_actual_revenue": True,
            "unknown_stays_unknown": True,
            "actual_revenue_requires_recognized_evidence": True,
            "external_execution_performed": False,
            "execution_authority": "none",
        },
        "revenue_operating_system": {
            "release_id": revenue_os.get("release_id"),
            "status": revenue_os.get("status"),
            "cycle_at": revenue_os.get("cycle_at"),
            "inventory_counts": dict(inventory_counts),
            "classified": inventory.get("classified"),
            "review_queue_count": len(revenue_os.get("review_queue") or []),
            "inventory_recovery": revenue_os.get("inventory_recovery"),
            "next_action": revenue_os.get("next_action"),
            "continuous_lead_generation": revenue_os.get("continuous_lead_generation"),
            "communications_execution": revenue_os.get("communications_execution"),
            "booking_execution": revenue_os.get("booking_execution"),
        },
        "predictive_cloud": {
            "available_component_count": cloud_available,
            "component_count": cloud_total,
            "availability_ratio": (
                round(cloud_available / cloud_total, 4)
                if cloud_total
                else None
            ),
            "unavailable_components": list(cloud.get("unavailable_components") or []),
            "stale_components": list(cloud.get("stale_components") or []),
            "component_matrix": component_matrix,
            "mode": cloud.get("mode"),
        },
        "predictive_engine": {
            "canonical_formula": "D*Q*E*OMEGA*B*O*C*T*P*F*LTV",
            "expected_revenue_value_formula": (
                "P_CLOSE*P_PAYMENT_GIVEN_CLOSE*P_FULFIL_GIVEN_PAYMENT*"
                "LTV*MARGIN*CAPACITY*RECENCY*CONFIDENCE*TIME_DISCOUNT"
                "-CAC-FULFILMENT_COST-RISK_COST"
            ),
            "quant_candidate_count": quant.get("candidate_count"),
            "decision_packets_ready": loop.get(
                "quant_decision_packet_available_count"
            ),
            "decision_packets_blocked": loop.get(
                "quant_decision_packet_unavailable_count"
            ),
            "missing_inputs": (
                quant.get("missing_field_counts")
                or loop.get("quant_missing_field_counts")
                or {}
            ),
            "prediction_state": (
                "EVIDENCE_INCOMPLETE"
                if _int(loop.get("quant_decision_packet_available_count")) == 0
                else "AVAILABLE"
            ),
            "predicted_is_actual_revenue": False,
            "execution_authority": "none",
        },
        "executive_intelligence": {
            "plan_id": astra.get("plan_id"),
            "primary_goal": (
                (astra.get("primary_goal") or {}).get("key")
                if isinstance(astra.get("primary_goal"), Mapping)
                else astra.get("primary_goal")
            ),
            "plan_step_count": astra.get("plan_step_count"),
            "auto_dispatch_eligible_count": astra.get("auto_dispatch_eligible_count"),
            "departments_in_plan": list(astra.get("departments_in_plan") or []),
            "goals": astra_goals[:8],
            "external_execution_performed": astra.get("external_execution_performed"),
        },
        "opportunity_intelligence": {
            "radar_candidate_count": loop.get("radar_candidate_count"),
            "research_observation_count": loop.get("research_observation_count"),
            "total_normalized_scores": loop.get("total_normalized_scores"),
            "factory_ready_count": loop.get("factory_ready_count"),
            "factory_blocked_count": loop.get("factory_blocked_count"),
            "quant_decision_packet_available_count": loop.get(
                "quant_decision_packet_available_count"
            ),
            "quant_decision_packet_unavailable_count": loop.get(
                "quant_decision_packet_unavailable_count"
            ),
            "quant_missing_field_counts": (
                quant.get("missing_field_counts")
                or loop.get("quant_missing_field_counts")
                or {}
            ),
            "prediction_state": (
                "EVIDENCE_INCOMPLETE"
                if _int(loop.get("quant_decision_packet_available_count")) == 0
                else "AVAILABLE"
            ),
            "actual_revenue": False,
        },
        "buyer_market": {
            "buyer_pool_count": len(buyer_team.get("buyer_pools") or []),
            "priority_target_count": len(buyer_team.get("priority_targets") or []),
            "product_demand_count": buyer_team.get("product_demand_count"),
            "sellable_product_demand_count": buyer_team.get(
                "sellable_product_demand_count"
            ),
            "buyer_seat_count": exchange.get("buyer_seat_count"),
            "corridor_count": exchange.get("corridor_count"),
            "inventory_count": exchange.get("inventory_count"),
            "exchange_inventory_ready_count": supply.get(
                "exchange_inventory_ready_count"
            ),
            "commercially_activated_buyers": capacity.get("commercially_activated"),
            "capacity_verified": capacity.get("capacity_verified"),
            "terms_verified": capacity.get("terms_verified"),
            "highest_priority_blocker": capacity.get("highest_priority_blocker"),
            "revenue_exchange_market_count": revenue_exchange.get("market_count"),
        },
        "commercial_catalog": {
            "product_count": catalog.get("product_count"),
            "active_count": catalog.get("active_count"),
            "binding_terms_ready_count": catalog.get("binding_terms_ready_count"),
            "active_binding_products": _active_catalog_products(catalog),
        },
        "enterprise_predictive_revenue": {
            "private_deployment": {
                **private_economics,
                "currency": "USD",
                "display_price": "$250,000+ starting floor",
                "truth_label": "FOUNDER_APPROVED_MODELLED_ECONOMICS_NOT_REVENUE",
            },
            "seed_target_count": enterprise_targets.get("target_count"),
            "enterprise_candidate_count": enterprise_pool.get(
                "total_enterprise_candidate_count"
            ),
            "eligible_rolling_candidate_count": enterprise_pool.get(
                "eligible_rolling_candidate_count"
            ),
            "targeted_retry_queued_count": enterprise_contacts.get(
                "targeted_retry_queued_count"
            ),
            "contact_intelligence_error_count": enterprise_contacts.get("error_count"),
            "targets": _enterprise_targets(enterprise_targets),
            "outreach_authorized": False,
            "actual_revenue": False,
        },
        "revenue_truth": {
            "window": current_window.get("label"),
            "acquisitions": current_window.get("acquisitions"),
            "qualified": current_window.get("qualified"),
            "buyer_reviews": current_window.get("buyer_reviews"),
            "delivered_outreach": current_window.get("delivered_outreach"),
            "commercial_replies": current_window.get("commercial_replies"),
            "commercial_terms": current_window.get("commercial_terms"),
            "verified_payments": current_window.get("verified_payments"),
            "fulfilments": current_window.get("fulfilments"),
            "recognized_revenue_cents": actual_revenue_cents,
            "realized_gp_cents": _int(revenue_truth.get("realized_gp_cents")),
            "highest_priority_blocker": pulse.get("highest_priority_blocker"),
            "pulse_state": pulse.get("pulse_state"),
            "forecast_included_in_truth": (
                revenue_truth.get("forecast_included_in_truth")
            ),
            "actual_revenue": actual_revenue_cents > 0,
        },
        "learning_loop": {
            "department_episode_count": memory.get("department_episode_count"),
            "outcome_conditioned_memory_count": memory.get(
                "outcome_conditioned_memory_count"
            ),
            "verified_outcomes_only": memory.get(
                "verified_outcomes_only_for_outcome_conditioned_memory"
            ),
            "model_weight_mutation_authorized": memory.get(
                "model_weight_mutation_authorized"
            ),
        },
        "settlement": {
            "asset": "USDT",
            "network": "BSC",
            "chain_id": 56,
            "payment_action": False,
        },
        "proof_chain": proof_chain,
        "source_state": sources,
        "execution_authority": "none",
        "side_effects": "none",
    }


def _money(cents: Any) -> str:
    try:
        value = int(cents)
    except (TypeError, ValueError):
        return "UNKNOWN"
    return f"${value / 100:,.0f}"


def render_predictive_revenue_demo_html(payload: Mapping[str, Any]) -> str:
    rev = payload.get("revenue_operating_system") or {}
    cloud = payload.get("predictive_cloud") or {}
    opp = payload.get("opportunity_intelligence") or {}
    engine = payload.get("predictive_engine") or {}
    buyers = payload.get("buyer_market") or {}
    enterprise = payload.get("enterprise_predictive_revenue") or {}
    truth = payload.get("revenue_truth") or {}
    catalog = payload.get("commercial_catalog") or {}
    executive = payload.get("executive_intelligence") or {}

    inventory = rev.get("inventory_counts") or {}
    target_rows = enterprise.get("targets") or []
    product_rows = catalog.get("active_binding_products") or []
    proof = payload.get("proof_chain") or []

    proof_html = "".join(
        f"""<div class="proof-step {'on' if row.get('observed') else 'off'}">
        <div class="proof-kicker">{escape(str(row.get('stage') or ''))}</div>
        <div class="proof-value">{escape(str(row.get('value') if row.get('value') is not None else _money(row.get('value_cents'))))}</div>
        <div class="proof-label">{escape(str(row.get('label') or ''))}</div>
        </div>"""
        for row in proof
    )
    target_html = "".join(
        f"""<div class="row"><div><strong>{escape(str(row.get('account_name') or 'Unknown'))}</strong>
        <span>{escape(str(row.get('account_type') or ''))}</span></div>
        <div class="tag">{escape(', '.join(str(x) for x in row.get('target_product_codes') or []) or 'research')}</div></div>"""
        for row in target_rows
    ) or "<div class='muted'>No enterprise targets available.</div>"

    component_html = "".join(
        f"""<span class="component {'on' if row.get('available') else 'off'}">
        {escape(str(row.get('component') or 'component'))}
        <small>{escape(str(row.get('freshness') or 'unknown'))}</small></span>"""
        for row in cloud.get("component_matrix") or []
    ) or "<span class='muted'>No component matrix available.</span>"

    missing_inputs = engine.get("missing_inputs") or {}
    missing_html = ", ".join(
        f"{escape(str(key))}: {escape(str(value))}"
        for key, value in sorted(missing_inputs.items())
    ) or "none"

    product_html = "".join(
        f"""<div class="row"><div><strong>{escape(str(row.get('product_name') or row.get('product_code') or 'Product'))}</strong>
        <span>{escape(str(row.get('product_family') or ''))}</span></div>
        <div class="tag">{escape(str(row.get('currency') or ''))} {_money(row.get('amount_cents'))}</div></div>"""
        for row in product_rows
    ) or "<div class='muted'>No binding-ready active products in snapshot.</div>"

    actual = _money(truth.get("recognized_revenue_cents"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI — Predictive Revenue Live Demo</title>
<style>
:root{{--bg:#07111f;--panel:#0c1b2e;--line:#1e3857;--text:#ecf4ff;--muted:#8da5bf;--accent:#61b4ff;--good:#45d483;--warn:#ffc761;--bad:#ff7383}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 20% 0,#12325a 0,#07111f 42%);color:var(--text);font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1500px;margin:auto;padding:34px}} .hero{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:24px}}
h1{{font-size:42px;line-height:1;margin:8px 0}} h2{{font-size:16px;margin:0 0 15px}} .eyebrow{{color:var(--accent);font-weight:800;letter-spacing:.16em;font-size:12px}}
.truth{{text-align:right}} .truth strong{{font-size:30px}} .muted,span{{color:var(--muted)}} .grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}}
.card{{background:rgba(12,27,46,.92);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 14px 45px #0005}}
.c3{{grid-column:span 3}} .c4{{grid-column:span 4}} .c6{{grid-column:span 6}} .c8{{grid-column:span 8}} .c12{{grid-column:span 12}}
.metric{{font-size:34px;font-weight:800;letter-spacing:-.04em}} .metric.good{{color:var(--good)}} .metric.warn{{color:var(--warn)}} .metric.bad{{color:var(--bad)}}
.proof{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}} .proof-step{{padding:14px;border-radius:12px;background:#0a1727;border:1px solid var(--line)}}
.proof-step.on{{border-color:#247a58}} .proof-step.off{{opacity:.65}} .proof-kicker{{font-size:10px;letter-spacing:.12em;color:var(--muted)}} .proof-value{{font-size:25px;font-weight:800}}
.proof-step.on .proof-value{{color:var(--good)}} .row{{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:10px 0;border-top:1px solid #17304c}} .row:first-child{{border-top:0}}
.row strong{{display:block}} .row span{{font-size:12px}} .tag{{font-size:11px;padding:5px 8px;border-radius:999px;border:1px solid #28517b;color:#acd6ff;max-width:46%;text-align:right}}
.pipeline{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}} .stage{{background:#081727;border-radius:12px;padding:12px;border:1px solid var(--line)}} .stage b{{font-size:24px;display:block}}
.guard{{border-left:4px solid var(--warn)}} .live{{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 18px var(--good);margin-right:7px}}
.formula{{font:700 18px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#bfe2ff;background:#071523;padding:14px;border-radius:12px;border:1px solid #21486e;overflow:auto}}
.components{{display:flex;flex-wrap:wrap;gap:7px}} .component{{font-size:11px;padding:7px 9px;border-radius:10px;border:1px solid #245d45;color:#bdf5d4;background:#092319}} .component.off{{border-color:#62404a;background:#29121b;color:#ffc2cb}} .component small{{display:block;color:var(--muted);font-size:9px}}
footer{{color:var(--muted);font-size:12px;margin-top:22px}} @media(max-width:900px){{.c3,.c4,.c6,.c8{{grid-column:span 12}} .proof,.pipeline{{grid-template-columns:1fr 1fr}} .hero{{display:block}} .truth{{text-align:left;margin-top:18px}}}}
</style></head>
<body><main>
<section class="hero"><div><div class="eyebrow"><span class="live"></span>LIVE SYSTEM · READ ONLY</div><h1>Predictive Revenue</h1>
<div class="muted">Signals → intelligence → opportunity → buyer → action → commercial truth → learning.</div></div>
<div class="truth"><div class="muted">Recognized revenue truth</div><strong>{actual}</strong><div class="muted">forecast/modelled value excluded</div></div></section>

<section class="card c12" style="margin-bottom:14px"><h2>Living proof chain</h2><div class="proof">{proof_html}</div></section>

<div class="grid">
<section class="card c3"><h2>Predictive Cloud</h2><div class="metric good">{escape(str(cloud.get('available_component_count') or 0))}/{escape(str(cloud.get('component_count') or 0))}</div><div class="muted">components available</div><div class="row"><span>Unavailable</span><b>{escape(str(len(cloud.get('unavailable_components') or [])))}</b></div><div class="row"><span>Stale</span><b>{escape(str(len(cloud.get('stale_components') or [])))}</b></div></section>
<section class="card c3"><h2>Astra Executive</h2><div class="metric">{escape(str(executive.get('plan_step_count') or 0))}</div><div class="muted">current plan steps</div><div class="row"><span>Auto-dispatch eligible</span><b>{escape(str(executive.get('auto_dispatch_eligible_count') or 0))}</b></div><div class="row"><span>Departments</span><b>{escape(str(len(executive.get('departments_in_plan') or [])))}</b></div></section>
<section class="card c3"><h2>Opportunity Intelligence</h2><div class="metric">{escape(str(opp.get('radar_candidate_count') or 0))}</div><div class="muted">radar candidates</div><div class="row"><span>Normalized scores</span><b>{escape(str(opp.get('total_normalized_scores') or 0))}</b></div><div class="row"><span>Quant packets ready</span><b>{escape(str(opp.get('quant_decision_packet_available_count') or 0))}</b></div></section>
<section class="card c3 guard"><h2>Current constraint</h2><div class="metric warn">{escape(str(buyers.get('terms_verified') or 0))}</div><div class="muted">verified buyer terms</div><div class="row"><span>Activated buyers</span><b>{escape(str(buyers.get('commercially_activated_buyers') or 0))}</b></div><div class="row"><span>Blocker</span><b>{escape(str(buyers.get('highest_priority_blocker') or 'UNKNOWN'))}</b></div></section>

<section class="card c12"><h2>Canonical Predictive Revenue Engine</h2>
<div class="formula">{escape(str(engine.get('canonical_formula') or 'UNKNOWN'))}</div>
<div class="row"><span>Prediction state</span><b>{escape(str(engine.get('prediction_state') or 'UNKNOWN'))}</b></div>
<div class="row"><span>Quant decision packets ready</span><b>{escape(str(engine.get('decision_packets_ready') or 0))}</b></div>
<div class="row"><span>Missing evidenced inputs</span><b style="max-width:70%;text-align:right">{missing_html}</b></div>
<div class="muted">The engine refuses to manufacture probability, timing or economics. Missing evidence stays UNKNOWN until the intelligence fabric resolves it.</div>
</section>

<section class="card c12"><h2>Live Predictive Cloud Components</h2><div class="components">{component_html}</div></section>

<section class="card c8"><h2>Autonomous Revenue Inventory</h2><div class="pipeline">
<div class="stage"><span>Raw</span><b>{escape(str(inventory.get('RAW_LEAD') or 0))}</b></div>
<div class="stage"><span>Pre-qualified</span><b>{escape(str(inventory.get('PREQUALIFIED_LEAD') or 0))}</b></div>
<div class="stage"><span>Qualified calls</span><b>{escape(str(inventory.get('QUALIFIED_CALL') or 0))}</b></div>
<div class="stage"><span>Appointments</span><b>{escape(str(inventory.get('BOOKED_APPOINTMENT') or 0))}</b></div>
<div class="stage"><span>CPA outcomes</span><b>{escape(str(inventory.get('CPA_OUTCOME') or 0))}</b></div>
</div><div class="row"><span>Current autonomous action</span><b>{escape(str((rev.get('next_action') or {}).get('action') or 'OBSERVE'))}</b></div></section>
<section class="card c4"><h2>Buyer Market</h2><div class="metric">{escape(str(buyers.get('buyer_seat_count') or 0))}</div><div class="muted">buyer seats observed</div><div class="row"><span>Corridors</span><b>{escape(str(buyers.get('corridor_count') or 0))}</b></div><div class="row"><span>Exchange-ready supply</span><b>{escape(str(buyers.get('exchange_inventory_ready_count') or 0))}</b></div><div class="row"><span>Verified capacity</span><b>{escape(str(buyers.get('capacity_verified') or 0))}</b></div></section>

<section class="card c6"><h2>Enterprise Predictive Revenue</h2><div class="metric good">$250,000+</div><div class="muted">founder-approved private deployment starting floor · modelled economics, not revenue</div>
<div class="row"><span>Enterprise seed targets</span><b>{escape(str(enterprise.get('seed_target_count') or 0))}</b></div><div class="row"><span>Enterprise candidate pool</span><b>{escape(str(enterprise.get('enterprise_candidate_count') or 0))}</b></div>{target_html}</section>
<section class="card c6"><h2>Commercial Products</h2><div class="metric">{escape(str(catalog.get('binding_terms_ready_count') or 0))}</div><div class="muted">binding-terms-ready catalog products</div>{product_html}</section>

<section class="card c12"><h2>Revenue truth — current 24h</h2><div class="pipeline">
<div class="stage"><span>Acquisitions</span><b>{escape(str(truth.get('acquisitions') or 0))}</b></div>
<div class="stage"><span>Qualified</span><b>{escape(str(truth.get('qualified') or 0))}</b></div>
<div class="stage"><span>Buyer reviews</span><b>{escape(str(truth.get('buyer_reviews') or 0))}</b></div>
<div class="stage"><span>Commercial replies</span><b>{escape(str(truth.get('commercial_replies') or 0))}</b></div>
<div class="stage"><span>Verified payments</span><b>{escape(str(truth.get('verified_payments') or 0))}</b></div>
</div></section>
</div>
<footer>Empire AI live read model · generated {escape(str(payload.get('generated_at') or ''))} · USDT/BSC settlement · predicted/modelled values are explicitly separate from recognized revenue.</footer>
</main></body></html>"""
