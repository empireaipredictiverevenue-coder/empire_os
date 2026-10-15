"""First-party buyer-enquiry consent must link to published privacy notice."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / 'apps/empire-public-site/src/app/commercial/page.tsx',
    ROOT / 'apps/empire-public-site/src/app/predictive-revenue/page.tsx',
)


@pytest.mark.parametrize('file', SOURCES)
def test_both_nonbinding_consent_forms_link_first_party_privacy_page(file):
    source = file.read_text()
    assert source.count('href="/privacy"') == 1
    assert source.count('type="checkbox"') == 1
    assert source.count('required') >= 1
    assert 'I consent to Empire AI emailing me about this specific' in source
    assert 'I am not signing up for unrelated marketing.' in source
    assert source.count('contact_consent:') == 1
    assert '/v1/checkout/' in source
    assert re.search(r'</label>\s*<p\b[^>]*>[^<]*<a href="/privacy"', source), (
        'privacy notice should be separately focusable, after the checkbox '
        'label and before the submit control'
    )
    privacy_position=source.index('href="/privacy"')
    # Predictive Revenue's existing form uses an implicit submit button;
    # do not require or change its working native button behaviour.
    submit_button=source.index('<button', privacy_position)
    assert privacy_position < submit_button
    assert 'href="http:' not in source
    assert 'window.localStorage' not in source
    assert 'document.cookie' not in source


def test_the_website_link_does_not_expand_granted_contact_scope():
    commercial=SOURCES[0].read_text()
    predict=SOURCES[1].read_text()
    for source in (commercial,predict):
        assert source.count('I am not signing up for unrelated marketing.') == 1
        assert 'marketing_consent: true' not in source
        assert 'analytics_opt_in: true' not in source
        assert '/r/' not in source
        assert 'action="http' not in source
    assert 'contact_consent: consent' in commercial
    assert 'contact_consent: contactConsent' in predict
