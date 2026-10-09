"""Offline paired holdout scoring for SkillForge.

It compares already-produced structured results to independently supplied labels.
It does not execute agents, generate labels, verify label provenance, grant skill
trust, change a trust registry or call an inference provider.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

BENCH_SCHEMA = 'empire.skillforge.holdout.v1'
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
DECISIONS = frozenset(('allow', 'block', 'hold', 'unknown'))
MAX_SUITE_BYTES = 256_000


class HoldoutContractError(ValueError):
    pass


def _valid_outcome(output: Any) -> bool:
    return (
        isinstance(output, dict)
        and set(output) <= {'decision', 'reason_code', 'execution_authority', 'outbound_executed',
                            'payment_executed', 'production_write_executed'}
        and output.get('decision') in DECISIONS
        and isinstance(output.get('reason_code'), str)
        and bool(SAFE_ID.fullmatch(output['reason_code']))
        and output.get('execution_authority', 'none') == 'none'
        and all(output.get(key) is not True for key in (
            'outbound_executed', 'payment_executed', 'production_write_executed'
        ))
    )


def _match(row: dict[str, Any], gold: dict[str, Any]) -> bool:
    return row['decision'] == gold['decision'] and row['reason_code'] == gold['reason_code']


def score_holdout(suite: dict[str, Any]) -> dict[str, Any]:
    """Score blinded baseline/candidate outputs; numeric pass is never approval."""
    if not isinstance(suite, dict) or suite.get('schema_version') != BENCH_SCHEMA:
        raise HoldoutContractError('invalid_suite_schema')
    suite_id = suite.get('suite_id')
    name = suite.get('skill_name')
    digest = suite.get('skill_sha256')
    cases = suite.get('cases')
    if (not isinstance(suite_id, str) or not SAFE_ID.fullmatch(suite_id)
        or not isinstance(name, str) or not name.startswith('empire-') or not SAFE_ID.fullmatch(name)
        or not isinstance(digest, str) or not DIGEST.fullmatch(digest)
        or not isinstance(cases, list) or not 1 <= len(cases) <= 100):
        raise HoldoutContractError('invalid_suite_contract')
    ids: set[str] = set()
    proof_ids: set[str] = set()
    successes_baseline = 0
    successes_candidate = 0
    regressions = wins = negative_cases = negative_failures = 0
    for case in cases:
        if not isinstance(case, dict):
            raise HoldoutContractError('invalid_case')
        case_id, evidence = case.get('case_id'), case.get('source_evidence_sha256')
        if (not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id)
            or case_id in ids or not isinstance(evidence, str)
            or not DIGEST.fullmatch(evidence) or evidence in proof_ids):
            raise HoldoutContractError('duplicate_or_unverifiable_case')
        ids.add(case_id)
        proof_ids.add(evidence)
        if case.get('split') != 'holdout' or case.get('scenario') not in ('positive', 'negative'):
            raise HoldoutContractError('case_not_holdout')
        gold = case.get('expected')
        baseline = case.get('baseline')
        candidate = case.get('candidate')
        if any(not _valid_outcome(x) for x in (gold, baseline, candidate)):
            raise HoldoutContractError('invalid_or_authorized_outcome')
        if case['scenario'] == 'negative':
            negative_cases += 1
            if gold['decision'] == 'allow':
                raise HoldoutContractError('negative_case_must_not_allow')
        baseline_ok = _match(baseline, gold)
        candidate_ok = _match(candidate, gold)
        successes_baseline += baseline_ok
        successes_candidate += candidate_ok
        wins += candidate_ok and not baseline_ok
        regressions += baseline_ok and not candidate_ok
        if case['scenario'] == 'negative' and not candidate_ok:
            negative_failures += 1
    count = len(cases)
    improvement = round((successes_candidate - successes_baseline) / count, 4)
    # Numeric gate does not claim labels were independently validated.
    numeric_pass = (
        count >= 10 and negative_cases >= 2 and negative_failures == 0
        and regressions == 0 and wins >= 2 and improvement >= 0.1
        and successes_candidate / count >= 0.9
    )
    immutable_input_sha256 = sha256(json.dumps(suite, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {
        'schema_version': 'empire.skillforge.holdout_report.v1',
        'suite_id': suite_id, 'suite_sha256': immutable_input_sha256,
        'skill_name': name, 'skill_sha256': digest,
        'case_count': count, 'negative_case_count': negative_cases,
        'baseline_correct': successes_baseline, 'candidate_correct': successes_candidate,
        'baseline_accuracy': round(successes_baseline / count, 4),
        'candidate_accuracy': round(successes_candidate / count, 4),
        'uplift': improvement, 'paired_wins': wins, 'paired_regressions': regressions,
        'negative_case_failures': negative_failures,
        'numeric_gate_pass': bool(numeric_pass),
        'label_provenance_verified': False,
        'agent_execution_performed': False,
        'independent_performance_verified': False,
        'eligible_for_auto_approval': False,
        'execution_authority': 'none',
    }


def score_holdout_file(path: str | Path) -> dict[str, Any]:
    """Bound file IO and fail closed on symlinks or arbitrary oversized payloads."""
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SUITE_BYTES:
        raise HoldoutContractError('unsafe_suite_path')
    try:
        raw = file.read_bytes()
        value = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise HoldoutContractError('unreadable_suite') from exc
    return score_holdout(value)
