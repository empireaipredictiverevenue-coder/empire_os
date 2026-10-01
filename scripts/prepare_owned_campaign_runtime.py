#!/usr/bin/env python3
"""Prepare an unpublished artifact, never change campaign state or a release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from empire_os.owned_campaign_content import prepare_marketing, render_asset
from empire_os.owned_campaign_preflight import digest, inspect_campaigns, _landing
from empire_os.owned_campaign_release import SCRIPT


def prepare(root, output, site_build='UNVERIFIED'):
    original = (root / 'runtime/astra/department_cycle_latest.json').read_bytes()
    marketing = json.loads(original)['marketing_growth']
    prepared = prepare_marketing(marketing, root)
    reference = ['docs/owned_campaign_activation_v2_delta.md']
    infrastructure = {k: {'status': 'PASS', 'evidence_refs': reference} for k in (
        'owned_destination', 'privacy_review', 'governed_enquiry_endpoint',
        'first_party_event_collector', 'public_route_prepared')}
    infrastructure['canonical_intake_schema'] = {
        'status': 'HELD_FOR_FOUNDER_DB_APPROVAL',
        'evidence_refs': ['migrations/empiredb/025_owned_campaign_intake.sql'],
        'detail': 'Repository schema lacks anonymous campaign observations and minimal enquiry ownership. No live schema application or role verification performed.'}
    infrastructure['site_build'] = {'status': site_build, 'evidence_refs': reference}
    report = inspect_campaigns(prepared, infrastructure)
    report.update(canonical_campaigns_sha256=digest(marketing['campaigns']),
                  prepared_campaigns_sha256=digest(prepared['campaigns']),
                  db_migration_required=True, db_migration_applied=False,
                  founder_db_approval_required=True, eligible_for_owned_deployment=False,
                  script_sha256=hashlib.sha256((root / SCRIPT).read_bytes()).hexdigest(),
                  public_owner_scopes=[c['public_owner_scope'] for c in prepared['campaigns']],
                  publication_reviews=[c['owned_publication_review'] for c in prepared['campaigns']],
                  live_verification='NOT_PERFORMED', campaign_state_mutated=False)
    # This output is a reviewable build artifact, not a business store or release.
    if output.resolve() == (root / 'runtime/astra').resolve() or 'out' in output.resolve().parts:
        raise ValueError('isolated preparation directory required')
    output.mkdir(parents=True, exist_ok=True)
    for c in prepared['campaigns']:
        (output / (c['campaign_id'] + '.html')).write_text(render_asset(_landing(c)))
    (output / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    if (root / 'runtime/astra/department_cycle_latest.json').read_bytes() != original:
        raise RuntimeError('campaign snapshot changed concurrently; discard prepared artifact')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--site-build', choices=['PASS', 'UNVERIFIED'], default='UNVERIFIED')
    args = p.parse_args()
    result = prepare(ROOT, args.output, args.site_build)
    print(json.dumps({k: result[k] for k in ['campaigns_requested', 'campaigns_preflight_passed', 'campaigns_blocked', 'db_migration_required']}))
