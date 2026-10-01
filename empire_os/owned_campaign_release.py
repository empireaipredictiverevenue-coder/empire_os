"""Read-only release gate. Preparation never creates the deployment release file."""
import hashlib
import json
from pathlib import Path

from empire_os.owned_campaign_content import prepare_marketing, render_asset
from empire_os.owned_campaign_preflight import digest, inspect_campaigns, _landing

ROOT = Path('/srv/empire_os')
RELEASE = Path('runtime/astra/owned_campaign_deployed_release.json')
SCRIPT = Path('apps/empire-public-site/public/research-runtime.js')


def load_release(root=ROOT):
    """Missing, stale, modified or not live-verified evidence exposes no routes."""
    try:
        release = json.loads((root / RELEASE).read_text())
        if release.get('deployment_verified') is not True or not release.get('deployment_evidence_refs'):
            return None
        current = json.loads((root / 'runtime/astra/department_cycle_latest.json').read_text())['marketing_growth']
        if release.get('canonical_campaigns_sha256') != digest(current['campaigns']):
            return None
        prepared = prepare_marketing(current, root)
        report = inspect_campaigns(prepared, release['infrastructure_review'])
        if report['campaigns_blocked'] or not report['campaigns_requested']:
            return None
        if release.get('script_sha256') != hashlib.sha256((root / SCRIPT).read_bytes()).hexdigest():
            return None
        expected = {c['campaign_id']: c['owned_publication_review']['asset_sha256'] for c in prepared['campaigns']}
        if release.get('asset_digests') != expected:
            return None
        return prepared
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return None


def released_html(campaign_id, root=ROOT):
    release = load_release(root)
    if release:
        for c in release['campaigns']:
            if c['campaign_id'] == campaign_id:
                return render_asset(_landing(c))
    return None


def released_paths(root=ROOT):
    release = load_release(root)
    return [f"/research/{c['campaign_id']}" for c in release['campaigns']] if release else []
