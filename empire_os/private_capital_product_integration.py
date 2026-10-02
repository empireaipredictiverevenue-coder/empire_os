"""Private Capital / Roll-Up Intelligence product integration foundation.

Architecture contract (bounded extension, OBSERVE only)
-------------------------------------------------------
Diagram: EmpireDB evidence -> tenant/provenance gate -> segments/member/target
 graph -> opportunity/deal-intent evidence -> enterprise review + proof blockers.
Placement: Market Intelligence / private_capital node, Control Fabric OBSERVE;
connects private_capital_intelligence deliverables to private_capital_rollup.
Existing snapshots count evidence but cannot establish evidence-backed graphs.
Upstream: caller-supplied canonical EmpireDB records, never legacy snapshots.
Downstream: internal product/Founder review consumers; no caller wiring here.
Truth: records carry canonical IDs, tenant, source reference, timezone-aware
observed_at, OBSERVED class and explicit claims. IDs are never manufactured.
The caller owns source authenticity; metadata validation cannot verify a source.
Company evidence alone never implies PE ownership, targeting or deal intent.
Schemas: company(id, name); segment(id, name); member(entity_id, segment_id);
portfolio(sponsor_id, company_id); target(sponsor_id, company_id, segment_id);
opportunity/deal_intent(company_id, statement). All require the common envelope
(id, tenant_id, backend='empiredb', evidence_class='OBSERVED', source_ref,
observed_at, kind); non-company kinds require domain='private_capital'.
Outputs are detached JSON-compatible derived views, not verified outcomes.
Persistence: none; EmpireDB remains canonical. Tenant is mandatory and isolated.
Execution: synchronous, bounded input, deterministic ordering, duplicate IDs
collapse only if identical; conflicting IDs are quarantined. No retries, I/O,
queues, external dependencies, funds, terms, sends, writes or authority changes.
Ownership: deterministic code builder; Astra may review, Needle may route;
focused tests verify. Only this worker owns the two scoped files.
Failure: reject invalid evidence and dangling links; report rejection reasons;
missing dependencies remain unknown. Disable caller use to roll back.
Observability: accepted source refs and rejection diagnostics in returned view;
no telemetry export or costs. Readiness means internal review only, never sell
permission. Paid proof stays blocked pending governed commercial-ledger and
fulfilment verification; observed intent is neither payment nor revenue.
Verification: focused/adjacent tests, compilation and diff review. Live runtime,
canonical evidence and Founder-surface verification remain promotion gates;
this foundation does not claim deployed or commercially proven completion.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping


_KINDS = {
    'company', 'segment', 'member', 'portfolio', 'target',
    'opportunity', 'deal_intent',
}
_FIELDS = {
    'company': ('name',),
    'segment': ('name',),
    'member': ('entity_id', 'segment_id'),
    'portfolio': ('sponsor_id', 'company_id'),
    'target': ('sponsor_id', 'company_id', 'segment_id'),
    'opportunity': ('company_id', 'statement'),
    'deal_intent': ('company_id', 'statement'),
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _reason(row: Mapping[str, Any], tenant_id: str) -> str | None:
    if row.get('tenant_id') != tenant_id:
        return 'tenant_mismatch'
    if row.get('backend') != 'empiredb':
        return 'noncanonical_backend'
    if row.get('evidence_class') != 'OBSERVED':
        return 'not_observed'
    if any(row.get(flag) is not False for flag in ('synthetic', 'mock', 'inferred') if flag in row):
        return 'non_observed_marker'
    kind = row.get('kind')
    if not isinstance(kind, str) or kind not in _KINDS:
        return 'unsupported_kind'
    if kind != 'company' and row.get('domain') != 'private_capital':
        return 'missing_private_capital_domain'
    if not all(_text(row.get(key)) for key in ('id', 'source_ref', 'observed_at', *_FIELDS[kind])):
        return 'missing_identity_or_provenance'
    try:
        observed = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00'))
        if observed.utcoffset() is None:
            return 'invalid_observed_at'
    except ValueError:
        return 'invalid_observed_at'
    if kind in {'portfolio', 'target'} and row['sponsor_id'] == row['company_id']:
        return 'self_relationship'
    return None


def build_private_capital_product_integration(
    evidence: Iterable[Mapping[str, Any]], *, tenant_id: str, max_records: int = 10000,
) -> dict[str, Any]:
    """Build a pure review view from explicit observed canonical evidence.

    ``source_ref`` must identify retained source evidence, not a guessed website.
    No network verification is attempted. Missing records mean UNKNOWN, not proof
    of absence. Input loss/iterator errors propagate; there is no fallback store.
    """
    if not _text(tenant_id):
        raise ValueError('tenant_id is required')
    if isinstance(max_records, bool) or not isinstance(max_records, int) or max_records < 1:
        raise ValueError('max_records must be a positive integer')
    rows: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    rejected: Counter[str] = Counter()
    for index, raw in enumerate(evidence):
        if index >= max_records:
            raise ValueError('bounded evidence limit exceeded')
        if not isinstance(raw, Mapping):
            rejected['invalid_record'] += 1
            continue
        reason = _reason(raw, tenant_id)
        if reason:
            rejected[reason] += 1
            continue
        # Keep only the contract fields, never arbitrary payload or credentials.
        row = {key: raw[key] for key in (
            'id', 'tenant_id', 'backend', 'evidence_class', 'source_ref',
            'observed_at', 'kind', *_FIELDS[raw['kind']],
        )}
        identity = row['id']
        if identity in rows and rows[identity] != row:
            conflicts.add(identity)
        else:
            rows[identity] = row
    for identity in conflicts:
        rows.pop(identity, None)
    rejected['conflicting_evidence_id'] += len(conflicts)
    companies = {key for key, row in rows.items() if row['kind'] == 'company'}
    segments = {key for key, row in rows.items() if row['kind'] == 'segment'}
    accepted: dict[str, list[dict[str, Any]]] = {kind: [] for kind in _KINDS}
    for identity in sorted(rows):
        row = rows[identity]
        company_refs = [row[key] for key in ('entity_id', 'company_id', 'sponsor_id') if key in row]
        if any(ref not in companies for ref in company_refs) or (
            'segment_id' in row and row['segment_id'] not in segments
        ):
            rejected['unresolved_reference'] += 1
            continue
        accepted[row['kind']].append(row)

    blockers = []
    for kind, blocker in (
        ('company', 'observed_company_evidence_missing'),
        ('segment', 'rollup_segmentation_missing'),
        ('member', 'segment_member_evidence_missing'),
        ('target', 'target_evidence_missing'),
        ('opportunity', 'opportunity_evidence_missing'),
        ('deal_intent', 'deal_intent_evidence_missing'),
    ):
        if not accepted[kind]:
            blockers.append(blocker)
    if any(rejected.values()):
        blockers.append('evidence_quality_review_required')
    proof_blockers = [
        'governed_enterprise_offer_approval_unverified',
        'buyer_acceptance_unverified',
        'delivery_acceptance_unverified',
        'settled_payment_unverified',
        'commercial_ledger_reconciliation_unverified',
    ]
    refs = sorted({row['source_ref'] for group in accepted.values() for row in group})
    return deepcopy({
        'schema_version': 'empire.private-capital-product-integration.v1',
        'tenant_id': tenant_id,
        'source': 'empiredb',
        'node_key': 'private_capital',
        'product_key': 'private_capital_intelligence',
        'commercial_product_key': 'private_capital_rollup',
        'mode': 'OBSERVE',
        'execution_authority': 'none',
        'evidence_state': 'EVIDENCE_AVAILABLE' if refs else 'UNKNOWN',
        'rollup_segments': accepted['segment'],
        'graph': {
            'companies': accepted['company'], 'members': accepted['member'],
            'portfolio': accepted['portfolio'], 'targets': accepted['target'],
        },
        'opportunities': accepted['opportunity'],
        'deal_intent_evidence': accepted['deal_intent'],
        'opportunity_count': len(accepted['opportunity']) or None,
        'deal_intent_observed': bool(accepted['deal_intent']),
        'enterprise_offer_readiness': {
            'state': 'READY_FOR_INTERNAL_REVIEW' if not blockers else 'BLOCKED',
            'blockers': blockers,
            'binding_terms_ready': False,
        },
        'paid_proof': {'state': 'UNVERIFIED', 'blockers': proof_blockers},
        'actual_revenue': False,
        'source_refs': refs,
        'rejections': {key: count for key, count in sorted(rejected.items()) if count},
        'unknown_stays_unknown': True,
    })
