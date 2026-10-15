"""Host canonicalization stays a review candidate; sensitive routes are held."""
from urllib.parse import urlsplit

import pytest

from empire_os.public_canonical_host_review import review_canonical_host_redirect


def review(path='/', *, method='GET', host='www.empire-ai.co.uk', query=''):
    return review_canonical_host_redirect(method=method,raw_host=host,
                                          raw_path=path,raw_query=query)


@pytest.mark.parametrize('path',[
    '/', '/trust', '/commercial', '/industries', '/industries/roofing',
    '/industries/solar', '/industries/hvac', '/industries/legal-mass-tort',
    '/predictive-revenue', '/privacy', '/terms',
    '/aeo/roofing/DFW', '/aeo/hvac/DFW/',
])
def test_exact_public_pages_have_candidate_to_same_path(path):
    row=review(path)
    assert row['eligible_for_site_owner_review'] is True
    assert row['proposed_http_status']==308
    assert row['proposed_location']=='https://empire-ai.co.uk'+path
    assert row['redirect_executed'] is False
    assert row['gateway_modified'] is False
    assert row['public_site_published'] is False
    assert row['execution_authority']=='none'
    assert urlsplit(row['proposed_location']).hostname=='empire-ai.co.uk'


@pytest.mark.parametrize('path',[
    '/buy','/checkout','/v1/search/search-console/status',
    '/v1/payments','/api/auth/callback/google',
    '/oauth/callback','/auth/login','/_next/static/app.js',
    '/.well-known/agent-card.json','/agent-web/tools/seo',
    '/r/test-referral-token','/v1/affiliate/status',
    '/roofing','/uk/roofing','/roofing/replacement-vs-repair',
    '/research/campaign_1234', '/research/agent-governance',
    '//evil.example','/industries/../buy',
    '/industries/roofing%2F..%2Fcheckout','/industries/roofing\\evil',
    '/health','/favicon.ico','/robots.txt','/sitemap.xml',
])
def test_all_sensitive_unpublished_or_ambiguous_paths_held(path):
    row=review(path)
    assert row['eligible_for_site_owner_review'] is False
    assert row['proposed_location'] is None
    assert row['proposed_http_status'] is None
    assert row['authentication_route_modified'] is False
    assert row['consumer_data_transferred'] is False
    assert row['gateway_owner_approval_required'] is True


@pytest.mark.parametrize('method',['POST','DELETE','PUT','PATCH','OPTIONS','TRACE','get',''])
def test_non_safe_methods_never_rewrite(method):
    assert review(method=method)['eligible_for_site_owner_review'] is False


@pytest.mark.parametrize('host',[
    'empire-ai.co.uk','evil.example','www.empire-ai.co.uk.evil.example',
    'WWW.EMPIRE-AI.CO.UK','www.empire-ai.co.uk:443','',
    'www.empire-ai.co.uk\r\nLocation: https://evil.example',
])
def test_never_base_redirect_on_arbitrary_or_malformed_host(host):
    assert review(host=host)['proposed_location'] is None


def test_head_only_candidate_no_response_execution():
    assert review(method='HEAD')['proposed_location']=='https://empire-ai.co.uk/'
    assert review(method='HEAD')['redirect_executed'] is False


def test_whitelisted_campaign_metadata_preserved_with_no_open_redirect():
    row=review('/industries/roofing',query='utm_source=organic&utm_campaign=US+roofing')
    assert row['proposed_location']=='https://empire-ai.co.uk/industries/roofing?utm_source=organic&utm_campaign=US+roofing'
    assert row['redirect_executed'] is False


@pytest.mark.parametrize('query',[
    'code=secret', 'state=oauth', 'next=https://evil.example',
    'utm_source=ok&destination=external',
    'utm_source=one&utm_source=two',
    'utm_source=abc%0D%0ALocation%3Ahttps%3A%2F%2Fevil.example',
    'utm_campaign=%2F%2Fevil.example',
    'utm_source=abc&&utm_medium=google',
    'utm_source=abc&gclid=test',
    'utm_source='+('A'*400),
])
def test_untrusted_query_or_sensitive_oauth_data_does_not_redirect(query):
    row=review('/trust',query=query)
    assert row['eligible_for_site_owner_review'] is False
    assert row['proposed_location'] is None


def test_candidate_never_claims_real_world_activation_or_indexation():
    approved=review('/industries/solar')
    denied=review('/v1/search')
    for r in (approved,denied):
        assert r['schema_version']=='empire.public.canonical_host_candidate.v1'
        assert r['state']=='REVIEW_ONLY'
        assert r['founder_release_approval_required'] is True
        assert r['gateway_owner_approval_required'] is True
        assert r['redirect_executed'] is False
        assert r['gateway_modified'] is False
        assert r['execution_authority']=='none'
