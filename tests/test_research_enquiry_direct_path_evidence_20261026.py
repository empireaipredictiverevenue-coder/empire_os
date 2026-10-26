from scripts import review_live_organic_buyer_journey_20261024 as audit
from tests.test_review_live_organic_buyer_journey_20261024 import zero_snapshot
from xml.etree.ElementTree import ParseError

FORM=b'''<section><p id="privacy">Submitting does not subscribe you to marketing.</p>
<form id="research-enquiry" method="post" action="/api/research/enquiry" aria-describedby="privacy">
<input name="reply_email" type="email" required>
<textarea name="research_question" required></textarea>
</form></section>'''

def fixture(*, form=FORM):
    paths=sorted(audit.PRIORITY|{"/research/sample"})
    def get(route):
        if route=="/robots.txt":
            return 200,{"Content-Type":"text/plain"},b"User-agent: *\nAllow: /\nSitemap: https://empire-ai.co.uk/sitemap.xml\n"
        if route=="/sitemap.xml":
            entries="".join("<url><loc>https://empire-ai.co.uk"+x+"</loc></url>" for x in paths)
            return 200,{"Content-Type":"text/xml"},("<urlset>"+entries+"</urlset>").encode()
        if route=="/v1/checkout/commercial/offers":
            return 200,{},b'{"offers":[{"id":1}]}'
        if route=="/v1/checkout/predictive-revenue/products":
            return 200,{},b'{"products":[{"id":1}]}'
        links=(b'<a href="/industries/roofing">Roofing</a>' if route=="/research/sample"
               else b'<a href="/commercial">Commercial</a>')
        page=(b'<html><head><link rel="canonical" href="https://empire-ai.co.uk'
              +route.encode()+b'"></head><body><main>'+links+
              (form if route=="/research/sample" else b'')+b'</main></body></html>')
        return 200,{"Content-Type":"text/html"},page
    return get

def test_genuine_existing_research_enquiry_not_an_indirect_missing_cta():
    result=audit.review(fixture(),zero_snapshot())
    assert result["existing_research_enquiry_form_pages"]==["/research/sample"]
    assert result["existing_research_enquiry_form_page_count"]==1
    assert "/research/sample" not in result["indirect_buyer_form_path_pages"]
    row=next(x for x in result["routes"] if x["route"]=="/research/sample")
    assert row["first_party_research_enquiry_form_present"] is True
    assert row["buyer_form_link_hops"]==2
    assert result["customer_submissions"]==0
    assert result["buyer_paths_proven_as_actual_visits"] is False
    assert result["research_form_present_does_not_verify_submission"] is True

def test_similar_unrelated_or_unconfirmed_forms_remain_gaps():
    variants=[
      FORM.replace(b'/api/research/enquiry',b'https://hostile.invalid/enquiry'),
      FORM.replace(b'method="post"',b'method="get"'),
      FORM.replace(b'id="privacy"',b'id="other"'),
      FORM.replace(b'aria-describedby="privacy"',b''),
      FORM.replace(b'name="reply_email"',b'name="other"'),
      FORM.replace(b'<textarea name="research_question" required>',
                   b'<textarea name="research_question">'),
      b'<form action="/api/research/enquiry" method="post"></form>',
    ]
    for form in variants:
        result=audit.review(fixture(form=form),zero_snapshot())
        assert "/research/sample" in result["indirect_buyer_form_path_pages"]
        assert result["existing_research_enquiry_form_page_count"]==0

def test_non_research_page_with_same_form_not_false_positive():
    m=audit.Markup()
    m.feed(FORM.decode())
    assert m.research_form_count==1
    assert m.research_form_email is True
