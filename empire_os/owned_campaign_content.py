"""Deterministic public research assets from current campaign evidence only."""
from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path

from empire_os.media_claim_verification import verify_owned_projection_claims
from empire_os.media_repurposing import duplication_guard
from empire_os.owned_campaign_preflight import digest

PRIVACY = ('We use your submitted details to respond to your enquiry. Submitting this form does NOT '
           'subscribe you to marketing. No automatic follow-up is sent. Please do not include sensitive personal information.')
# Editorial research methods, not external facts or market assertions.
GUIDES = {
 'competitor_coverage:denver-co-roofing:denver, co': (
  'Denver roofing: how to audit a coverage gap',
  'A practical source-coverage worksheet for Denver roofing, with a clear separation between missing evidence and demand.',
  'An evidence gap is a question about what has been collected. Use this worksheet to decide which roofing sources need a closer look before drawing a competitive conclusion.',
  'Coverage audit worksheet',
  'Create one row per source with its URL, retrieval date, service description, geographic statement and the passage supporting each entry. Leave a blank where a page cannot be reached. Record inaccessible pages separately from pages that explicitly exclude a service. Neither condition establishes the size of a market.',
  'How should the sample be defined?',
  'Write down why each roofing source belongs in the Denver comparison. Separate directory listings from business-owned descriptions. Decide whether the comparison concerns service coverage, content coverage or search visibility before collecting more pages; these answer different questions.',
  'Which missing passages would change the interpretation? Can each geographic statement be traced to a dated source? Does the same collection method reproduce the gap?',
  'This approach may help a reader choose the next source to inspect instead of treating missing coverage as an opportunity already proven.'),
 'market:class action lawyer:atlanta': (
  'Atlanta class-action research: testing an intelligence brief',
  'A research brief for Atlanta class-action intelligence: define the question, separate operational evidence and assess possible product fit.',
  'Start with the decision an intelligence brief would support. This page offers a way to frame that decision without treating an internal review or delivered message as evidence of demand.',
  'Build a decision brief',
  'Specify the research question, the intended reader and the evidence that would make the answer usable. Keep legal subject matter, geographic scope and collection dates in separate fields. Ask for source passages supporting each proposed finding. Do not include client names, case details or sensitive personal information in an initial enquiry.',
  'How would a pilot be evaluated?',
  'Before discussing fit, define a small output that can be inspected: a source list, a gap analysis or an evidence summary. Agree on what counts as relevant evidence and what remains unresolved. A catalog entry provides an offer identity; it does not establish that this audience needs it or that any engagement has been accepted.',
  'What decision needs support? Which source types would be acceptable? What exclusions keep the brief focused? What evidence would show the proposed output is unsuitable?',
  'A bounded brief may make a product-fit conversation more precise while preserving the distinction between research interest and commercial acceptance.'),
 'market:general_contractor:nyc': (
  'NYC general-contractor research: an evidence-chain checklist',
  'Trace acquisition, qualification and delivery references separately in NYC general-contractor research without inferring buyer intent.',
  'Several kinds of operational evidence can appear in one research record. Use the checklist here to examine what each kind can answer and which links still need proof.',
  'Separate the evidence chain',
  'Create separate columns for source acquisition, qualification rationale and delivery status. An acquisition entry answers where a record came from. A qualification reference needs its own criteria and date. A delivery entry is not a reply. Do not count these entries as independent businesses or combine them into a conversion numerator without a verified identity join.',
  'Define the denominator before a rate',
  'Write down the population, inclusion rules and time window before attempting to calculate a response or conversion rate. Record duplicate handling explicitly. If the denominator or identity join is absent, retain the observations as a list of evidence to inspect rather than presenting a percentage.',
  'Which records share a verified identity? What qualification criteria were applied? Is there a genuine inbound response? Which time window would support a fair comparison?',
  'Separating the chain may prevent operational activity from being mistaken for customer interest and makes the next evidence request easier to specify.'),
 'market:hvac:dallas-fort worth': (
  'Dallas–Fort Worth HVAC: scoping an opportunity-intelligence pilot',
  'Define a Dallas–Fort Worth HVAC research scope, evidence acceptance criteria and an explicit stop rule before discussing managed-service fit.',
  'A useful pilot discussion starts with a bounded question. This guide helps distinguish what an intelligence output should contain from claims about sales, demand or delivery outcomes.',
  'Write the acceptance criteria first',
  'Describe the territory in words the reviewer can apply consistently. List the HVAC service categories to include and the categories to exclude. Request dated provenance for each proposed observation. Choose a review sample and document reasons for rejecting irrelevant entries; do not equate the number of entries with demand.',
  'Keep a stop rule in the research plan',
  'State which missing evidence would stop the pilot discussion: unclear source rights, ambiguous identity, unsupported geographic coverage or an output that cannot answer the original question. Treat delivery references as operational context only. Request a separate fit assessment before considering scope, commercial terms or any commitment.',
  'What territory definition can both parties apply? Which source evidence would make an observation usable? Who would assess the output? What uncertainty must remain visible?',
  'Explicit acceptance criteria may reduce ambiguity in a fit discussion without promising an outcome or implying a customer relationship.'),
 'market:hvac:denver, co': (
  'Denver HVAC: from acquired records to a research question',
  'A source-validation guide for Denver HVAC research that keeps acquired inventory distinct from verified demand or product fit.',
  'An acquired record is a starting point for investigation. This guide sets out a sequence for checking relevance before using inventory to support a broader claim.',
  'Validate relevance in stages',
  'First record where the item originated and when it was collected. Next inspect whether the source actually describes an HVAC activity in the intended geography. Keep uncertain matches unresolved. Finally identify the decision the item could inform; if no decision is clear, retain it as inventory rather than assigning commercial significance.',
  'Keep the unknowns visible',
  'Use an evidence log with columns for source, observed wording, unresolved identity, geographic support and next check. Mark missing information as unknown, not negative. Do not borrow qualification or response evidence from another city or campaign to fill a gap in the Denver record.',
  'Can the original source be inspected? Is the activity described relevant to the research scope? What independent evidence would justify qualification? Is any product match actually established?',
  'This staged review may help readers identify the smallest next check needed before making a demand or suitability claim.'),
}


DECISION_CHECKS = {
 'competitor_coverage:denver-co-roofing:denver, co': 'Decision rule for a coverage review: label an item source unavailable when retrieval fails, scope unclear when the wording is ambiguous, and supported only when a dated passage answers the chosen question. Keep those categories separate in the final worksheet. Before comparing sources, check whether they were collected using the same inclusion rules. A directory snippet and a complete business page should not silently receive the same evidential weight. Stop at a request for more evidence if the comparison cannot be reproduced; do not turn an incomplete sample into a ranking.',
 'market:class action lawyer:atlanta': 'A practical brief can end with three decisions: whether the question is answerable from the permitted sources, whether an intelligence summary would help the intended reader, and whether a proposed pilot needs further scoping. Record the reason for each decision and the unresolved evidence beside it. Keep an unsuitable result as a valid research outcome. The brief should remain useful even if no engagement follows. For an initial conversation, share the research question and source requirements rather than personal case information or an assumed budget.',
 'market:general_contractor:nyc': 'Use a join audit before interpreting the chain. For each proposed connection, record the identifiers used, the system that owns the identity and whether the match is confirmed or ambiguous. Leave unmatched records in separate groups. Then ask whether every observation belongs to the same campaign and observation window. A delivered item with no independently observed response ends the chain at delivery. A qualification label with no visible criteria remains an unresolved reference. This produces an audit trail a second reader can inspect without assuming that all operational records represent conversions.',
 'market:hvac:dallas-fort worth': 'A pilot scope worksheet should contain an inclusion example, an exclusion example, a source-provenance requirement and a named review decision. These are fields to complete with real evidence, not sample businesses to invent. Ask whether the same rule would classify a borderline item consistently. Record disagreements before expanding the scope. If the intended reviewer cannot explain how an observation would be used, revise the question before discussing an engagement. Success criteria for research should describe the usefulness and traceability of the output, without substituting a promised revenue result.',
 'market:hvac:denver, co': 'Use a progression log with one decision at each step: source recoverable, description relevant, geographic scope supported, identity resolved, and research use defined. Do not mark later steps complete merely because an earlier step passed. Record the date and supporting passage when a step changes. If only acquisition provenance is available, the honest endpoint is a source-validation task. Keep that endpoint distinct from a sales opportunity. A reader can use the log to request precisely the missing evidence without accepting an implied product recommendation or market forecast.',
}


def public_owner_scope(c):
    scope = c.get('tenant_scope') or {}
    resolved = (c.get('account_label') == 'Empire AI' and c.get('account_id') is None
                and c.get('tenant_id') is None and scope.get('account_id') is None
                and scope.get('tenant_id') is None and scope.get('customer_access_authorized') is False)
    return {'status': 'PUBLIC_OWNER_SCOPE_RESOLVED' if resolved else 'UNRESOLVED',
            'account_label': c.get('account_label'), 'ownership_scope': 'empire_owned' if resolved else None,
            'account_id': c.get('account_id'), 'tenant_id': c.get('tenant_id'),
            'customer_tenant': None, 'customer_access_authorized': False,
            'customer_tenant_resolved': False}


def source_projection(root, ref):
    path, sha = ref.split('#sha256=', 1)
    if path not in ('runtime/opportunity_radar/latest.json', 'runtime/commercial_catalog/latest.json'):
        raise ValueError('unsupported evidence owner')
    obj = json.loads((root / path).read_text())
    # Existing Revenue Distribution provenance uses json.dumps(sort_keys=True).
    actual = hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
    if actual != sha:
        raise ValueError('source projection changed; rebuild campaign evidence first')
    return obj



def _projection_ref(path, payload):
    sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"{path}#sha256={sha}"


def refresh_source_bindings(marketing, root):
    """Rebind unpublished campaign refs only when canonical identity still matches."""
    result = deepcopy(marketing)
    radar_path = 'runtime/opportunity_radar/latest.json'
    catalog_path = 'runtime/commercial_catalog/latest.json'
    radar = json.loads((root / radar_path).read_text())
    catalog = json.loads((root / catalog_path).read_text())
    radar_ref = _projection_ref(radar_path, radar)
    catalog_ref = _projection_ref(catalog_path, catalog)
    radar_rows = radar.get('candidates') or []
    products = catalog.get('products') or []

    for campaign in result.get('campaigns') or []:
        key = campaign.get('opportunity_key')
        opportunity = [
            row for row in radar_rows
            if isinstance(row, dict) and row.get('opportunity_key') == key
        ]
        if len(opportunity) != 1:
            raise ValueError('opportunity identity changed; rebuild required')

        refs = [
            ref for ref in (campaign.get('opportunity_evidence_refs') or [])
            if not str(ref).startswith(radar_path + '#sha256=')
            and not str(ref).startswith(catalog_path + '#sha256=')
        ]
        refs.append(radar_ref)

        product_refs = [
            ref for ref in (campaign.get('product_evidence_refs') or [])
            if not str(ref).startswith(catalog_path + '#sha256=')
        ]
        if campaign.get('product_code') == 'managed_service':
            pid = campaign.get('product_id')
            matches = [
                product for product in products
                if isinstance(product, dict)
                and product.get('product_id') == pid
                and product.get('product_code') == 'managed_service'
                and product.get('catalog_state') == 'VERIFIED'
                and product.get('active') is True
            ]
            if len(matches) != 1:
                raise ValueError('verified product identity changed; rebuild required')
            refs.append(catalog_ref)
            product_refs.append(catalog_ref)
        elif campaign.get('product_code') is not None or campaign.get('product_id') is not None:
            raise ValueError('unsupported product binding')

        campaign['opportunity_evidence_refs'] = list(dict.fromkeys(refs))
        campaign['product_evidence_refs'] = list(dict.fromkeys(product_refs))

    return result

def build_asset(c, root):
    refs = c['opportunity_evidence_refs']
    radar_ref = next(r for r in refs if r.startswith('runtime/opportunity_radar/latest.json#sha256='))
    radar = source_projection(root, radar_ref)
    matches = [o for o in radar['candidates'] if o.get('opportunity_key') == c['opportunity_key']]
    if len(matches) != 1 or not set(matches[0]['evidence_refs']).issubset(refs):
        raise ValueError('opportunity provenance mismatch')
    o = matches[0]
    title, description, summary, method_title, method, context_title, context, questions, why = GUIDES[c['opportunity_key']]
    claims = [
        {'kind': 'segment', 'text': f"Empire's current research projection identifies {o['niche']} in {o['metro']} as a research segment.", 'evidence_refs': [radar_ref]},
        {'kind': 'source', 'text': f"The recorded evidence class is {o['evidence_strength']}; the source owner is {o['source']}.", 'evidence_refs': [radar_ref]},
    ]
    product = None
    if c.get('product_code') == 'managed_service':
        catalog_ref = next(r for r in c['product_evidence_refs'] if '#sha256=' in r)
        products = source_projection(root, catalog_ref)['products']
        products = [p for p in products if p.get('product_id') == c['product_id'] and p.get('product_code') == 'managed_service' and p.get('catalog_state') == 'VERIFIED' and p.get('active') is True]
        if len(products) != 1 or 'managed_service' not in o.get('products', []):
            raise ValueError('verified product match required')
        product = products[0]
        claims.append({'kind': 'catalog', 'text': f"Empire's verified catalog names {product['product_name']} in the {product['product_family']} family.", 'evidence_refs': [catalog_ref]})
    elif c.get('product_code') is not None or c.get('product_id') is not None:
        raise ValueError('unsupported product')
    limitations = ('This is a research guide based on an internal source projection, not an independently verified market report. '
                   'Search demand, customer problems, audience fit, conversion rates and market share remain unknown. '
                   'Source activity does not establish buyer demand, accepted pricing, a customer relationship or revenue. '
                   'The underlying records are internal provenance references, not public proof of the claims they may contain.')
    a = {'asset_type': 'landing_page', 'asset_id': c['campaign_id'] + ':landing',
         'campaign_id': c['campaign_id'], 'h1': title, 'seo_title': title,
         'meta_description': description, 'thesis': summary,
         'claims': claims, 'copy': {'claims': []},
         'evidence_refs': list(dict.fromkeys(refs + c.get('product_evidence_refs', []))),
         'product_refs': c.get('product_evidence_refs', []),
         'cta': 'Discuss product fit' if product else 'Enquire about the research',
         'privacy_notice': PRIVACY, 'internal_links': ['/trust', '/industries'],
         'sections': [
             {'heading': 'Executive summary', 'body': summary},
             {'heading': 'What Empire observed', 'body': ' '.join(x['text'] for x in claims[:2])},
             {'heading': method_title, 'body': method},
             {'heading': 'Market / research context: ' + context_title, 'body': context},
             {'heading': 'Limitations / what is not yet known', 'body': limitations},
             {'heading': 'Decision worksheet', 'body': DECISION_CHECKS[c['opportunity_key']]},
             {'heading': 'Why this may matter', 'body': why},
             {'heading': 'Research questions / next evidence needed', 'body': questions},
         ]}
    if product:
        a['sections'].append({'heading': 'Managed-service fit', 'body': claims[-1]['text'] + ' This page makes no further capability or outcome claim. Discuss the research scope before considering an engagement.'})
    else:
        a['sections'].append({'heading': 'Research only', 'body': 'No product match is established for this campaign. An enquiry asks about the research; it is not a product order.'})
    return a, verify_owned_projection_claims(claims, campaign=c, opportunity=o, catalog_product=product)


def render_asset(a):
    e = escape
    sections = ''.join(f'<section><h2>{e(s["heading"])}</h2><p>{e(s["body"])}</p></section>' for s in a['sections'])
    refs = ''.join(f'<li><code>{e(r)}</code></li>' for r in a['evidence_refs'])
    links = ''.join(f'<a href="{e(p)}">{e(p.strip("/").replace("-", " ").title())}</a> ' for p in a['internal_links'])
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(a["seo_title"])}</title><meta name="description" content="{e(a["meta_description"], quote=True)}">'
            f'<link rel="canonical" href="https://empire-ai.co.uk/research/{a["campaign_id"]}">'
            '<style>body{max-width:780px;margin:2rem auto;padding:0 1rem;font:18px/1.65 system-ui;color:#17212b;background:#fafafa}h1{line-height:1.2}section{margin:2rem 0}code{font-size:12px;overflow-wrap:anywhere}label{display:block;margin:1rem 0}input,textarea{display:block;width:95%;padding:.6rem;font:inherit}button{padding:.7rem 1rem;font:inherit}nav a{margin-right:1rem}</style><script src="/research-runtime.js" defer></script></head><body><header><a href="/">Empire AI</a></header><main>'
            f'<h1>{e(a["h1"])}</h1>{sections}<section><h2>Evidence / sources</h2><p>Internal provenance identifiers; no external source was fetched for this page.</p><ul>{refs}</ul></section>'
            f'<nav aria-label="Related information">{links}</nav><section><h2>{e(a["cta"])}</h2>'
            f'<p id="privacy">{e(a["privacy_notice"])}</p><form id="research-enquiry" aria-describedby="privacy" action="/api/research/enquiry" method="post">'
            f'<input type="hidden" name="campaign_id" value="{e(a["campaign_id"])}"><input type="hidden" name="asset_id" value="{e(a["asset_id"])}">'
            '<label>Reply email <input type="email" name="reply_email" required maxlength="254" autocomplete="email"></label>'
            '<label>Research question <textarea name="research_question" required minlength="10" maxlength="4000"></textarea></label>'
            '<label>Company (optional) <input name="company" maxlength="200" autocomplete="organization"></label>'
            '<label>Role (optional) <input name="role" maxlength="100"></label>'
            f'<button type="submit">{e(a["cta"])}</button><p role="status" id="receipt"></p></form>'
            '<noscript>The enquiry form requires JavaScript. You can read all research and limitations without submitting.</noscript>'
            '</section></main></body></html>')


def review_asset(c, a, root, other_assets=()):
    expected, claims = build_asset(c, root)
    html = render_asset(a)
    quality = duplication_guard(candidate={'title': a['seo_title'], 'hook': a['thesis']},
        historical_items=[{'title': x['seo_title'], 'hook': x['thesis']} for x in other_assets])
    standalone = (a == expected and len(' '.join(s['body'] for s in a['sections']).split()) >= 300
                  and not quality['duplicate_risk'])
    passed = standalone and claims['status'] == 'PASS' and a['privacy_notice'] == PRIVACY
    return {'status': 'PASS' if passed else 'BLOCKED', 'campaign_id': c['campaign_id'],
            'asset_id': a['asset_id'], 'asset_sha256': hashlib.sha256(html.encode()).hexdigest(),
            'asset_contract_sha256': digest(a), 'evidence_refs': a['evidence_refs'],
            'claim_inventory': a['claims'], 'claim_verification_result': claims,
            'independent_visitor_value': standalone, 'limitations_present': a == expected,
            'privacy_surface_present': a['privacy_notice'] == PRIVACY,
            'brand_quality_review': quality, 'review_owner': 'media_claim_verification+media_repurposing'}


def prepare_marketing(marketing, root):
    result = refresh_source_bindings(marketing, root)
    assets = [build_asset(c, root)[0] for c in result['campaigns']]
    for c, a in zip(result['campaigns'], assets):
        c['assets'] = [a if old.get('asset_type') == 'landing_page' else old for old in c['assets']]
        c['public_owner_scope'] = public_owner_scope(c)
        c['owned_publication_review'] = review_asset(c, a, root, [x for x in assets if x != a])
    return result
