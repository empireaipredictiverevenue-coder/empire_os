from pathlib import Path
import importlib.util
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "guarded_four_industry_links",
    ROOT/"scripts/release_guarded_four_industry_links_20261026.py",
)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture_html(slug):
    return (f'<html><head><title>Owned {slug}</title>'
            f'<link rel="canonical" href="https://empire-ai.co.uk/industries/{slug}"/></head>'
            '<body><main><h1>Original headline</h1>'
            '<section class="relative z-10">'
            '<div><p>CONNECTED INTELLIGENCE</p><h2>Original subhead</h2>'
            '<div class="mt-9 flex flex-wrap justify-center gap-3">'
            '<a href="/industries/solar" class="group inline-flex items-center">'
            'Existing link<svg height="24"><path d="M5 12h14"></path></svg></a>'
            '</div></div></section><p>Unrelated original content.</p></main></body></html>')


@pytest.mark.parametrize("slug,expected",[
    ("roofing",2),("hvac",3),("property",2),("legal-mass-tort",1),
])
def test_exact_additional_anchors_no_changes_elsewhere(slug,expected):
    original=fixture_html(slug)
    output,inserted=mod.transform(slug,original.encode())
    data=output.decode()
    assert data.replace(inserted,"",1)==original
    assert len(inserted)>0
    assert data.count('>Original headline<')==1
    assert data.count('>Unrelated original content.<')==1
    assert sum(data.count('href="'+href+'"') for _,href in mod.LINKS[slug])==expected
    assert 'href="/industries/solar"' in data


def test_duplicate_or_missing_panel_fails_closed():
    bad=fixture_html("roofing").replace(
        '<p>CONNECTED INTELLIGENCE</p>',
        '<p>NOT FOUND</p>',
    )
    with pytest.raises(ValueError,match="contextual_section_not_unique"):
        mod.transform("roofing",bad.encode())
    duplicate=fixture_html("roofing").replace(
        '</div></div></section>',
        '<a href="/aeo/roofing/DFW/">dup</a></div></div></section>'
    )
    with pytest.raises(ValueError,match="link_already_published"):
        mod.transform("roofing",duplicate.encode())


def test_staging_has_no_unapproved_pages():
    assert set(mod.LINKS)=={"roofing","hvac","property","legal-mass-tort"}
    assert sum(map(len,mod.LINKS.values()))==8
    assert all(href.startswith(("/research/","/aeo/"))
               for rows in mod.LINKS.values() for _,href in rows)
