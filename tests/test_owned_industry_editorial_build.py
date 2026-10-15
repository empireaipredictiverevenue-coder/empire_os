"""SEO pillar static-export proof must not manufacture click or buyer authority."""
from pathlib import Path
import pytest

from scripts.verify_owned_industry_editorial_build import EXPECTED, verify_build


def fixture_html(slug, *, canonical=True, link='/commercial', extra='', noindex=False):
    heading, section, faq = EXPECTED.get(slug, ('Other', 'Other section', 'Other question'))
    robots = '<meta name="robots" content="noindex,nofollow">' if noindex else ''
    canon = f'<link rel="canonical" href="https://empire-ai.co.uk/industries/{slug}">' if canonical else ''
    return (f'<html><head><title>Empire industry intelligence</title>{canon}{robots}</head>'
            f'<body><main><h1>{slug.title()} intelligence</h1><section>'
            f'<h2>{heading}</h2><h3>{section}</h3><h3>{faq}</h3>'
            f'<a href="{link}">Request a scoped proposal</a>{extra}'
            '</section></main></body></html>')


def seeded(tmp_path):
    industry=tmp_path/'industries'
    industry.mkdir()
    for slug in ('roofing','solar','hvac','property'):
        (industry/f'{slug}.html').write_text(fixture_html(slug))
    (tmp_path/'roofing.html').write_text('<html><head><meta name="robots" content="noindex,nofollow"></head><body></body></html>')
    return tmp_path


def test_local_verified_static_export_never_claims_live_publication(tmp_path):
    result=verify_build(seeded(tmp_path))
    assert result['schema_version']=='empire.seo.industry_editorial_build_proof.v1'
    assert result['status']=='STATIC_EXPORT_REVIEWED_NOT_LIVE'
    assert result['buyer_roofing_noindex_held'] is True
    assert result['public_site_deployed'] is False
    assert result['execution_authority']=='none'
    assert result['paid_click_routing'] is False
    assert result['lead_delivery_enabled'] is False
    assert result['funds_moved'] is False
    assert set(result['industry_pages'])=={'roofing','solar'}


@pytest.mark.parametrize(('slug','change','reason'),[
    ('roofing','canonical','incorrect_canonical'),
    ('solar','commercial','existing_founder_form_link_missing'),
    ('roofing','external','unapproved_click_or_call_destination'),
    ('solar','phone','unapproved_click_or_call_destination'),
    ('roofing','payer','unapproved_click_or_call_destination'),
    ('roofing','missing','expected_editorial_missing'),
    ('solar','nofollow','approved_b2b_pillar_unintentionally_noindexed'),
])
def test_invalid_or_commercially_unsafe_export_fails(tmp_path,slug,change,reason):
    root=seeded(tmp_path)
    path=root/'industries'/f'{slug}.html'
    text=path.read_text()
    if change=='canonical':text=text.replace('rel="canonical"','rel="alternate"')
    if change=='commercial':text=text.replace('href="/commercial"','href="/unknown"')
    if change=='external':text=text.replace('</section>','<a href="http://buyer.example">paid click</a></section>')
    if change=='phone':text=text.replace('</section>','<a href="tel:+10000000000">Call</a></section>')
    if change=='payer':text=text.replace('</section>','<a href="/r/affiliate">commission</a></section>')
    if change=='missing':text=text.replace(EXPECTED['roofing'][0],'Unrelated vague text')
    if change=='nofollow':text=text.replace('</head>','<meta name="robots" content="noindex"></head>')
    path.write_text(text)
    with pytest.raises(ValueError,match=reason):verify_build(root)


def test_unapproved_consumer_buyer_landing_noindex_protects_all_publication(tmp_path):
    root=seeded(tmp_path)
    (root/'roofing.html').write_text('<html><head></head><body>Route live</body></html>')
    with pytest.raises(ValueError,match='consumer_roofing_noindex_hold_missing'):
        verify_build(root)


def test_copy_cannot_be_laundered_onto_other_industry_pages(tmp_path):
    root=seeded(tmp_path)
    p=root/'industries'/'hvac.html'
    p.write_text(p.read_text().replace('</section>',f'<p>{EXPECTED["solar"][0]}</p></section>'))
    with pytest.raises(ValueError,match='industry_copy_spread_to_unrelated_page'):
        verify_build(root)


def test_no_symlink_crossing_site_export_root(tmp_path):
    root=seeded(tmp_path)
    page=root/'industries'/'roofing.html'
    other=root/'offlimits.html'
    other.write_text(page.read_text())
    page.unlink()
    page.symlink_to(other)
    with pytest.raises(ValueError,match='bounded_real_static_export_file_required'):
        verify_build(root)
