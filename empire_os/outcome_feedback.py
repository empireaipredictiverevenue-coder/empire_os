"""Phase 3F feedback normalization for revenue intelligence and Astra."""
from __future__ import annotations

from statistics import mean
from typing import Any, Iterable, Mapping


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def feedback_to_revenue_features(row: Mapping[str, Any]) -> dict[str, Any]:
    conversion = str(row.get("conversion_outcome") or "unknown").lower()
    actual_revenue = bool(row.get("actual_revenue"))
    satisfaction = row.get("buyer_satisfaction")
    replied = conversion not in {"unknown", "no_response"}

    return {
        "replied": replied,
        "engaged": conversion in {"qualified", "booked", "won"},
        "previous_purchase": actual_revenue,
        "conversion_probability_target": (
            1.0 if conversion == "won"
            else 0.0 if conversion in {"lost", "no_response"}
            else None
        ),
        "buyer_satisfaction": (
            round(_num(satisfaction), 2) if satisfaction is not None else None
        ),
        "actual_revenue_cents": int(_num(row.get("actual_revenue_cents"))),
        "actual_cost_cents": int(_num(row.get("actual_cost_cents"))),
        "gross_profit_cents": int(_num(row.get("gross_profit_cents"))),
        "fulfilment_order_id": row.get("fulfilment_order_id"),
        "prospect_id": row.get("prospect_id"),
        "buyer_id": row.get("buyer_id"),
        "opportunity_id": row.get("opportunity_id"),
    }


def summarize_outcomes(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(rows)
    converted = [
        row for row in items
        if str(row.get("conversion_outcome") or "").lower() == "won"
    ]
    satisfaction = [
        _num(row.get("buyer_satisfaction"))
        for row in items
        if row.get("buyer_satisfaction") is not None
    ]
    revenue = sum(int(_num(row.get("actual_revenue_cents"))) for row in items)
    cost = sum(int(_num(row.get("actual_cost_cents"))) for row in items)
    profit = sum(int(_num(row.get("gross_profit_cents"))) for row in items)

    return {
        "orders": len(items),
        "converted": len(converted),
        "conversion_rate": round(len(converted) / len(items), 4) if items else 0.0,
        "actual_revenue_cents": revenue,
        "actual_cost_cents": cost,
        "gross_profit_cents": profit,
        "gross_margin_rate": round(profit / revenue, 4) if revenue > 0 else 0.0,
        "average_buyer_satisfaction": (
            round(mean(satisfaction), 2) if satisfaction else None
        ),
    }


def build_verified_outcome_feedback(twin, *, tenant_id, as_of, canonical_work=None):
    """Scoped adaptation of canonical full records; no RPC projection inference."""
    from copy import deepcopy
    from datetime import datetime
    from empire_os.cortex_learning_loop import build_cortex_learning_packet

    def timestamp(value):
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone-aware evidence required')
        return parsed

    if not isinstance(tenant_id, str) or not tenant_id.strip() or twin.get('tenant_id') != tenant_id:
        raise ValueError('outcome feedback tenant mismatch or missing')
    now = timestamp(as_of.isoformat() if isinstance(as_of, datetime) else as_of)
    packet = build_cortex_learning_packet(twin)
    if packet['label']['available'] is not True:
        raise ValueError('verified commercial learning label required')
    ref = packet['label']['outcome_ref']
    outcome = next(row for row in reversed(twin['outcomes']['history'])
                   if 'canonical:commercial_outcomes:' + str(row.get('id')) == ref)
    evidence = outcome.get('evidence') or {}
    if not isinstance(evidence, Mapping) or outcome.get('verified') is False:
        raise ValueError('invalid canonical outcome evidence')
    actual_time = timestamp(outcome.get('recorded_at'))
    available_times = [actual_time]
    if actual_time > now:
        raise ValueError('future outcome evidence')
    order = outcome.get('fulfilment_order_id')
    commercial = twin.get('commercial') or {}
    for group, fields in (('payment_evidence', ('verified_at',)),
                          ('fulfilment_orders', ('delivered_at', 'confirmed_at', 'outcome_at'))):
        for row in commercial.get(group) or []:
            if row.get('tenant_id') != tenant_id:
                raise ValueError('commercial evidence tenant mismatch or missing')
            if any(timestamp(row[key]) > now for key in fields if row.get(key)):
                raise ValueError('future commercial evidence')
            available_times.extend(timestamp(row[key]) for key in fields if row.get(key))
    if packet['label']['value'] == 1:
        if not any(row.get('id') == order and (row.get('delivered_at') or row.get('confirmed_at'))
                   for row in commercial.get('fulfilment_orders') or []):
            raise ValueError('outcome fulfilment linkage missing')
        if not any(row.get('fulfilment_order_id') == order and row.get('transaction_hash') and row.get('verified_at')
                   for row in commercial.get('payment_evidence') or []):
            raise ValueError('outcome payment linkage missing')
    truth = twin.get('revenue_truth') or {}
    order_record = next((row for row in commercial.get('fulfilment_orders') or [] if row.get('id') == order), {})
    causal = evidence.get('causal_lineage')
    if causal is not None:
        from empire_os.decision_identity import validate_causal_lineage, causal_lineage_from_work
        causal = validate_causal_lineage(causal)
        if causal['tenant_id'] != tenant_id or causal['opportunity_id'] != order_record.get('opportunity_id'):
            raise ValueError('outcome causal tenant or opportunity mismatch')
        if causal != (order_record.get('commercial_payload') or {}).get('causal_lineage'):
            raise ValueError('outcome lineage contradicts canonical order')
        if any(key in evidence and evidence[key] != causal[key] for key in causal if key != 'schema_version'):
            raise ValueError('contradictory outcome lineage field')
        if canonical_work is None:
            raise ValueError('outcome causal lineage requires canonical work read')
        expected = causal_lineage_from_work(canonical_work, tenant_id=tenant_id,
            opportunity_key=causal['opportunity_key'], opportunity_id=causal['opportunity_id'])
        if expected != causal:
            raise ValueError('outcome lineage contradicts canonical work')
        if causal['execution_performed'] and timestamp(canonical_work.get('updated_at')) > actual_time:
            raise ValueError('execution evidence learned after outcome')
    revenue = cost = profit = None
    if packet['label']['value'] == 1:
        if truth.get('tenant_id') != tenant_id or truth.get('fulfilment_order_id') != order:
            raise ValueError('order-level revenue lineage required')
        if truth.get('actual_revenue') is not True or not any(str(ref).startswith('canonical:commercial_events:')
                for ref in truth.get('evidence_refs') or []):
            raise ValueError('recognized revenue event provenance required')
        if timestamp(truth.get('recognized_at')) > now:
            raise ValueError('future recognized revenue')
        available_times.append(timestamp(truth['recognized_at']))
        for value in truth.get('evidence_available_at') or []:
            time = timestamp(value)
            if time > now:
                raise ValueError('future recognized revenue evidence availability')
            available_times.append(time)
        revenue = truth.get('recognized_revenue_cents')
        if truth.get('actual_cost_verified') is True:
            if not truth.get('actual_cost_evidence_refs'):
                raise ValueError('actual cost provenance required')
            cost = truth.get('actual_cost_cents')
            profit = truth.get('realized_gp_cents')
            if any(type(value) is not int for value in (revenue, cost, profit)) or cost < 0 or profit != revenue - cost:
                raise ValueError('inconsistent verified realized economics')
    lineage = {key: (causal if causal is not None else evidence).get(key) for key in
               ('opportunity_key', 'prediction_ref', 'decision_ref', 'execution_ref')}
    packet['learning_lineage'] = dict(lineage, tenant_id=tenant_id, outcome_ref=ref)
    if causal is not None:
        packet['learning_lineage']['causal_lineage'] = deepcopy(causal)
    packet['verification'].update(actual_cost_cents=cost, gross_profit_cents=profit,
        actual_revenue_cents=revenue, available_at=max(available_times).isoformat(),
        outcome_recorded_at=actual_time.isoformat())
    packet['label']['evidence_refs'] = list(dict.fromkeys([
        *packet['label']['evidence_refs'], *truth.get('evidence_refs', []),
        *truth.get('actual_cost_evidence_refs', [])]))
    return dict(lineage, schema_version='empire.verified_outcome_feedback.v1',
        tenant_id=tenant_id, entity_id=twin.get('entity_id'), outcome_ref=ref,
        fulfilment_order_id=order, product_id=order_record.get('product_id'),
        buyer_id=order_record.get('buyer_id'), prospect_id=order_record.get('prospect_id'),
        outcome_recorded_at=actual_time.isoformat(), conversion_outcome=outcome['conversion_outcome'],
        available_at=max(available_times).isoformat(),
        verified_label=packet['label']['value'], verified_outcome=True, synthetic=False,
        actual_revenue=packet['label']['value'] == 1, actual_revenue_cents=revenue,
        actual_cost_cents=cost, gross_profit_cents=profit,
        evidence_refs=deepcopy(packet['label']['evidence_refs']), cortex_packet=deepcopy(packet),
        causal_lineage=deepcopy(causal),
        learning_stage='LEARNING_CANDIDATE', shadow_only=True, execution_authority='none')


def validate_verified_feedback(feedback, *, tenant_id, as_of):
    """Validate scoped learning at consumer boundaries; refs are not authenticity."""
    from datetime import datetime
    if not tenant_id or feedback.get('tenant_id') != tenant_id:
        raise ValueError('verified feedback tenant mismatch or missing')
    packet = feedback.get('cortex_packet') or {}
    label = packet.get('label') or {}
    verification = packet.get('verification') or {}
    ref = feedback.get('outcome_ref')
    if (feedback.get('schema_version') != 'empire.verified_outcome_feedback.v1'
            or feedback.get('verified_outcome') is not True or feedback.get('synthetic') is not False
            or feedback.get('shadow_only') is not True or feedback.get('execution_authority') != 'none'
            or packet.get('tenant_id') != tenant_id or label.get('available') is not True
            or label.get('synthetic') is not False or label.get('forecast_derived') is not False
            or not isinstance(ref, str) or not ref.startswith('canonical:commercial_outcomes:')
            or not ref.removeprefix('canonical:commercial_outcomes:')
            or ref != label.get('outcome_ref') or ref not in feedback.get('evidence_refs', ())
            or feedback.get('verified_label') != label.get('value')):
        raise ValueError('unverified feedback cannot enter learning')
    if label.get('value') == 1 and not all(verification.get(key) is True for key in
            ('payment_verified', 'fulfilment_verified', 'recognized_revenue')):
        raise ValueError('verified win requires payment fulfilment recognized revenue')
    if feedback.get('conversion_outcome') not in ('won', 'lost', 'no_response'):
        raise ValueError('terminal outcome required')
    expected = 1 if feedback['conversion_outcome'] == 'won' else 0
    if type(feedback.get('verified_label')) is not int or feedback['verified_label'] != expected:
        raise ValueError('outcome label mismatch')
    for key in ('actual_revenue_cents', 'actual_cost_cents', 'gross_profit_cents', 'available_at', 'outcome_recorded_at'):
        if feedback.get(key) != verification.get(key):
            raise ValueError('verified feedback actuals or temporal evidence mismatch')
    lineage = packet.get('learning_lineage') or {}
    if feedback.get('causal_lineage') is not None:
        from empire_os.decision_identity import validate_causal_lineage
        causal = validate_causal_lineage(feedback['causal_lineage'])
        if lineage.get('causal_lineage') != causal or any(causal[key] != feedback.get(key)
                for key in ('tenant_id', 'opportunity_key', 'prediction_ref', 'decision_ref', 'execution_ref')):
            raise ValueError('verified feedback causal lineage mismatch')
    if any(lineage.get(key) != feedback.get(key) for key in
           ('tenant_id', 'opportunity_key', 'prediction_ref', 'decision_ref', 'execution_ref', 'outcome_ref')):
        raise ValueError('feedback lineage mismatch')
    actual = datetime.fromisoformat(feedback['available_at'].replace('Z', '+00:00'))
    now = datetime.fromisoformat(as_of.replace('Z', '+00:00')) if isinstance(as_of, str) else as_of
    if actual.tzinfo is None or now.tzinfo is None or actual > now:
        raise ValueError('future or unscoped outcome time')


def build_verified_feedback_from_records(*, order, outcome, payment_evidence, revenue_event,
                                         tenant_id, as_of, canonical_work=None):
    """Canonical full-record runtime handoff to the existing V2B truth gate."""
    from copy import deepcopy
    if not order.get('id') or outcome.get('fulfilment_order_id') != order['id']:
        raise ValueError('canonical outcome/order linkage required')
    for row in (order, outcome):
        if row.get('tenant_id') is not None and row['tenant_id'] != tenant_id:
            raise ValueError('canonical record tenant mismatch')
        if row.get('synthetic') is True or row.get('forecast_derived') is True or row.get('verified') is False:
            raise ValueError('unverified canonical commercial record')
    if (outcome.get('evidence') or {}).get('tenant_id') not in (None, tenant_id):
        raise ValueError('canonical outcome evidence tenant mismatch')
    for proof in payment_evidence:
        if proof.get('synthetic') is True or proof.get('forecast_derived') is True or proof.get('verified') is False:
            raise ValueError('unverified canonical payment evidence')
    causal = (order.get('commercial_payload') or {}).get('causal_lineage')
    if causal is not None and (outcome.get('evidence') or {}).get('causal_lineage') != causal:
        raise ValueError('canonical outcome causal lineage mismatch')
    truth = {'available': False}
    if revenue_event is not None:
        event = revenue_event
        payload = event.get('payload') or {}
        if (not event.get('id') or event.get('event_type') != 'revenue_recognized'
                or event.get('tenant_id') not in (None, tenant_id)
                or event.get('fulfilment_order_id') != order['id']
                or event.get('opportunity_id') != order.get('opportunity_id')
                or payload.get('actual_revenue') is not True
                or payload.get('synthetic') is True or payload.get('forecast_derived') is True
                or payload.get('causal_lineage') != causal):
            raise ValueError('independent canonical recognized revenue evidence required')
        if type(event.get('amount_cents')) is not int or event['amount_cents'] <= 0:
            raise ValueError('canonical recognized revenue amount required')
        if payload.get('settlement_source') not in ('direct_payment', 'escrow_release'):
            raise ValueError('verified settlement source required')
        matching = [row for row in payment_evidence if row.get('id') == payload.get('evidence_id')
                    and row.get('transaction_hash') == payload.get('transaction_hash')
                    and row.get('fulfilment_order_id') == order['id']]
        if not matching:
            raise ValueError('recognized revenue payment evidence mismatch')
        cost = payload.get('actual_cost_evidence') or {}
        cost_refs = []
        availability = [event.get('created_at') or event['occurred_at']]
        if payload.get('actual_cost_evidence_verified') is True:
            if cost.get('fulfilment_order_id') != order['id'] or cost.get('actual_cost_ready') is not True:
                raise ValueError('actual cost order evidence required')
            for kind in ('acquisition_cost', 'fulfilment_cost'):
                row = cost.get(kind) or {}
                if (not row.get('evidence_id') or row.get('source_type') not in ('provider_invoice', 'internal_actual')
                        or type(row.get('amount_cents')) is not int or row['amount_cents'] < 0):
                    raise ValueError('verified actual cost evidence required')
                observed = str(row.get('observed_at') or '')
                from datetime import datetime
                clock = datetime.fromisoformat(observed.replace('Z', '+00:00'))
                limit = datetime.fromisoformat(as_of.replace('Z', '+00:00')) if isinstance(as_of, str) else as_of
                if clock.tzinfo is None or clock > limit:
                    raise ValueError('future actual cost evidence')
                cost_refs.append('canonical:commercial_evidence_registry:' + row['evidence_id'])
                availability.append(observed)
            if sum(cost[k]['amount_cents'] for k in ('acquisition_cost', 'fulfilment_cost')) != event.get('cost_cents'):
                raise ValueError('recognized actual cost mismatch')
        truth = dict(available=True, tenant_id=tenant_id, fulfilment_order_id=order['id'], actual_revenue=True,
            recognized_at=event['occurred_at'], recognized_revenue_cents=event.get('amount_cents'),
            actual_cost_cents=event.get('cost_cents'), realized_gp_cents=event.get('margin_cents'),
            actual_cost_verified=bool(cost_refs), actual_cost_evidence_refs=cost_refs,
            evidence_available_at=availability,
            evidence_refs=['canonical:commercial_events:' + event['id']])
    twin = dict(tenant_id=tenant_id, entity_id=order.get('entity_id'),
        outcomes={'history': [{**deepcopy(outcome), 'tenant_id': tenant_id}]},
        commercial={'fulfilment_orders': [{**deepcopy(order), 'tenant_id': tenant_id}],
                    'payment_evidence': deepcopy(payment_evidence)}, revenue_truth=truth)
    return build_verified_outcome_feedback(twin, tenant_id=tenant_id, as_of=as_of, canonical_work=canonical_work)
