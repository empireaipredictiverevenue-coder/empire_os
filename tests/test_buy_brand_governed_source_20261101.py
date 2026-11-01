"""Existing Design Studio / ASTRA founder-lockup source guard.

Source-only brand rollout test: the published /buy HTML is managed by the
original root website release; it can legitimately remain at its previous
pinned version until the protected scoped transaction is complete.
"""
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]
COMPONENT=ROOT/"apps/empire-public-site/src/components/BrandLockup.tsx"
ASSET=ROOT/"apps/empire-public-site/public/brand/empire-ai-primary-orbital-a-founder-approved.png"
CHROME=ROOT/"apps/empire-public-site/src/components/SiteChrome.tsx"
BUY=ROOT/"apps/empire-public-site/src/app/buy/page.tsx"
EXPECTED_SHA="55e98ad2ae182991d95908738135779102beb81818cd7c3607a3a49e1f2aa596"


def test_original_founder_horizontal_lockup_is_exact_not_recreated():
    assert ASSET.is_file() and not ASSET.is_symlink()
    assert hashlib.sha256(ASSET.read_bytes()).hexdigest()==EXPECTED_SHA
    s=COMPONENT.read_text()
    assert 'src="/brand/empire-ai-primary-orbital-a-founder-approved.png"' in s
    assert 'width="820"' in s and 'height="160"' in s
    assert "Empire AI — Predictive Revenue Infrastructure" in s
    assert 'empire-orbital-a-reference-mark.webp' not in s
    assert 'empire-mark.svg' not in s


def test_original_shared_chrome_reuses_one_canonical_logo_source():
    s=CHROME.read_text()
    assert 'import BrandLockup from "./BrandLockup"' in s
    assert '<BrandLockup />' in s
    assert 'aria-label="Empire AI home"' in s
    assert 'site-footer' in s


def test_current_checkout_and_financial_ux_unchanged_by_brand_source():
    s=BUY.read_text()
    for required in (
        'fetch("/v1/checkout/catalog")',
        'CREATE PAYMENT REQUEST',
        'BSC payer wallet',
        'terms_accepted: accepted',
        'idempotency_key:',
        'Payment request awaiting independent approval',
    ):
        assert required in s,required
