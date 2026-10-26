"""Bounded, noncommercial first-party buyer due diligence.

Website links, page status and hashes are evidence to REVIEW, not verified
contract terms, payout, contact identity, acceptance or outbound authority.
The public web is untrusted. No form submission, mail, CRM or vendor API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit
import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.request

from empire_os.buyer_network_research_rotation import accepted_domain

MAX_PAGE_BYTES = 750_000
MAX_LINKS = 7
# One existing scheduled worker serves the opened <=500 company research
# queue. Eight bounded sites per cycle, retaining enough legitimate recent
# observations to cover the 131+ source-verified company portfolio.
MAX_DOMAINS_PER_CYCLE = 8
MAX_HISTORY_DOMAINS = 256
RECHECK_SECONDS = 24 * 3600
HOLD_RECHECK_SECONDS = 6 * 3600
RESULT_TTL_SECONDS = 7 * 24 * 3600
PROMOTION_EVIDENCE_MAX_AGE = 48 * 3600
CATEGORIES = ('terms', 'privacy', 'compliance', 'rules', 'contact', 'integration', 'publisher')
CRITICAL = frozenset(('terms', 'privacy', 'compliance', 'rules', 'contact'))
_HTTP_TIMEOUT = 5
_SAFE_PATH = re.compile(r'^/[A-Za-z0-9._/~%-]{0,179}$')


class DueDiligenceError(ValueError):
    pass


class _StrictRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, domain: str):
        self.domain = domain
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if (target.scheme != 'https'
            or not _host_allowed(self.domain, target.hostname)
            or target.port not in (None, 443)
            or target.username or target.password
            or not public_dns_only(target.hostname or '')):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _host_allowed(domain: str, hostname: str | None) -> bool:
    return bool(hostname and hostname.lower().rstrip('.') in (domain, 'www.' + domain))


def public_dns_only(domain: str) -> bool:
    if (not domain or domain.startswith('www.') and not accepted_domain(domain[4:])):
        return False
    if not accepted_domain(domain.removeprefix('www.')):
        return False
    try:
        records=socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
        return bool(records) and all(ipaddress.ip_address(item[4][0]).is_global for item in records)
    except (OSError, ValueError):
        return False


def safe_page_url(domain: str, href: str, *, base_url: str | None = None) -> str | None:
    if not isinstance(href, str) or not 0 < len(href) <= 500:
        return None
    if href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
        return None
    url = urljoin(base_url or 'https://' + domain + '/', href.strip())
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not _host_allowed(domain, parts.hostname)
            or parts.port not in (None, 443)
            or parts.username or parts.password
            or not _SAFE_PATH.fullmatch(parts.path or '/')):
            return None
    except ValueError:
        return None
    # Discard query and fragment: these often contain private tracking tokens.
    return urlunsplit(('https', parts.hostname.lower(), parts.path or '/', '', ''))


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]]=[]
        self.current: list[Any] | None=None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current=[dict(attrs).get('href', ''), []]

    def handle_data(self, text):
        if self.current is not None and len(self.current[1]) < 50:
            self.current[1].append(text[:160])

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            if len(self.links) < 500:
                self.links.append((str(self.current[0] or ''), ' '.join(self.current[1])[:190]))
            self.current=None


class _VisibleText(HTMLParser):
    """Collect bounded visible text; skip scripts, forms and embedded code."""
    SKIP = frozenset(('script','style','noscript','svg','form','textarea','input'))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth=0
        self.words=[]
        self.size=0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth+=1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth-=1

    def handle_data(self, data):
        if self.skip_depth or self.size>100_000:
            return
        snippet=data[:1500]
        self.size+=len(snippet)
        self.words.append(snippet)


def observed_topics(html: str) -> list[str]:
    """Keywords observed, never independently verified commercial promises."""
    parser=_VisibleText()
    parser.feed(html[:MAX_PAGE_BYTES])
    text=' '.join(' '.join(parser.words).casefold().split())
    patterns={
        'PAYOUT_LANGUAGE':r'\b(?:payouts?|revenue share|revshare|cost per call|\bcpl\b|\bcpa\b)\b',
        'CONSENT_LANGUAGE':r'\b(?:tcpa|consent|opt.in|privacy policy|trustedform|jornaya)\b',
        'INTEGRATION_LANGUAGE':r'\b(?:ping.post|api integration|api documentation|webhook|lead routing|host.post)\b',
        'AI_OR_ML_DATA_TERMS_LANGUAGE':r'\b(?:artificial intelligence|machine learning|train(?:ing)? (?:a |any )?model|\bai\b systems)\b',
    }
    return sorted(key for key,pattern in patterns.items() if re.search(pattern,text))


def category_for_link(label: str, path: str) -> str | None:
    text=(label + ' ' + path).lower().replace('-', ' ').replace('_', ' ')
    if any(word in text for word in ('terms of service', 'terms of use', ' terms', 'terms/', '/terms', 'buyer terms')):
        return 'terms'
    if 'privacy' in text:
        return 'privacy'
    if any(word in text for word in ('tcpa', 'compliance', 'consent policy')):
        return 'compliance'
    if any(word in text for word in ('marketplace rules', 'quality guidelines', 'publisher rules', 'lead guidelines')):
        return 'rules'
    if any(word in text for word in ('contact us', 'contact', 'get in touch')):
        return 'contact'
    if any(word in text for word in ('api docs', 'api documentation', 'integration', 'ping post', 'ping/post', 'technical spec')):
        return 'integration'
    if any(word in text for word in ('publishers', 'publisher', 'affiliate program', 'sell leads', 'partner application')):
        return 'publisher'
    return None


def linked_first_party_pages(domain: str, html: str, *, final_url: str | None = None) -> list[dict[str,str]]:
    parser=_Links()
    parser.feed(html[:MAX_PAGE_BYTES])
    pages={}
    for href,label in parser.links:
        url=safe_page_url(domain, href, base_url=final_url)
        if not url or url.rstrip('/') in ('https://'+domain, 'https://www.'+domain):
            continue
        category=category_for_link(label, urlsplit(url).path)
        if not category:
            continue
        key=(category,url)
        if key not in pages:
            pages[key]={'category':category,'url':url}
    ranked=sorted(pages.values(),key=lambda x:(CATEGORIES.index(x['category']),len(x['url']),x['url']))
    chosen=[]
    seen=set()
    for page in ranked:
        if page['category'] in seen or page['url'] in (x['url'] for x in chosen):
            continue
        chosen.append(page)
        seen.add(page['category'])
        if len(chosen)>=MAX_LINKS:
            break
    return chosen


def fetch_public_page(domain: str, url: str) -> dict[str,Any]:
    """GET verified-public HTTPS page; no automatic external redirects or raw logs."""
    expected=safe_page_url(domain, url)
    if expected is None or expected!=url or not public_dns_only(urlsplit(url).hostname or ''):
        return {'url':url[:250], 'status':'NOT_PUBLIC','http_status':None}
    context=ssl.create_default_context()
    opener=urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), _StrictRedirect(domain),
    )
    req=urllib.request.Request(url,method='GET',headers={
        'User-Agent':'EmpireAI-FirstPartyBuyerDueDiligence/1.0 (public research; read-only)',
        'Accept':'text/html,application/xhtml+xml',
    })
    try:
        with opener.open(req, timeout=_HTTP_TIMEOUT) as reply:
            final=reply.geturl()
            if safe_page_url(domain,final) is None:
                return {'url':url,'status':'UNSAFE_REDIRECT','http_status':None}
            content_type=reply.headers.get('Content-Type','').lower()
            if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                return {'url':url,'status':'UNSUPPORTED_TYPE','http_status':int(reply.status)}
            raw=reply.read(MAX_PAGE_BYTES+1)
            partial=len(raw)>MAX_PAGE_BYTES
            if partial:
                raw=raw[:MAX_PAGE_BYTES]
            charset=reply.headers.get_content_charset() or 'utf-8'
            try:
                html=raw.decode(charset,errors='replace')
            except LookupError:
                html=raw.decode('utf-8',errors='replace')
            return {
                'url':url, 'final_url':safe_page_url(domain,final),
                'status':('PARTIAL_PASS' if partial else 'PASS')
                         if 200<=reply.status<300 else 'HTTP_ERROR',
                'http_status':int(reply.status),
                'body_sha256':sha256(raw).hexdigest(),
                'capture_truncated':partial,
                # Private in-memory only; scrubbed from saved snapshots.
                '_html':html,
            }
    except urllib.error.HTTPError as exc:
        return {'url':url,'status':'HTTP_ERROR','http_status':int(exc.code)}
    except (OSError,ValueError,TimeoutError,ssl.SSLError) as exc:
        return {'url':url,'status':'UNAVAILABLE','http_status':None,
                'error_type':type(exc).__name__}


def observe_domain(domain: str, *, fetch:Callable[[str,str],dict[str,Any]]=fetch_public_page,
                   now_epoch:float | None = None) -> dict[str,Any]:
    """One bounded first-party public-web observation, never a buyer approval."""
    if not accepted_domain(domain):
        raise DueDiligenceError('invalid_first_party_domain')
    from time import time
    stamp=now_epoch if now_epoch is not None else time()
    base='https://'+domain+'/'
    home=fetch(domain,base)
    if not isinstance(home,dict):
        raise DueDiligenceError('invalid_fetch_contract')
    if home.get('url') != base:
        raise DueDiligenceError('homepage_source_mismatch')
    home_state={k:v for k,v in home.items() if k in ('url','final_url','status','http_status','body_sha256','error_type','capture_truncated')}
    source_topic_urls={key:[] for key in ('PAYOUT_LANGUAGE','CONSENT_LANGUAGE',
                                          'INTEGRATION_LANGUAGE','AI_OR_ML_DATA_TERMS_LANGUAGE')}
    def topics_from(page):
        if page.get('status') not in ('PASS','PARTIAL_PASS'):
            return
        html=page.get('_html')
        if isinstance(html,str):
            for topic in observed_topics(html):
                source_topic_urls[topic].append(page['url'])
    topics_from(home)
    links=[]
    if home.get('status') in ('PASS','PARTIAL_PASS') and isinstance(home.get('_html'),str):
        links=linked_first_party_pages(domain,home['_html'],
                         final_url=home.get('final_url') or base)
    checks=[]
    for item in links[:MAX_LINKS]:
        check=fetch(domain,item['url'])
        if not isinstance(check,dict) or check.get('url') != item['url']:
            raise DueDiligenceError('linked_source_mismatch')
        topics_from(check)
        checks.append({**item, **{k:v for k,v in check.items()
                  if k in ('status','http_status','final_url','body_sha256','error_type','capture_truncated')}})
    broken=[{'category':x['category'],'url':x['url'],'http_status':x['http_status']}
            for x in checks if x['category'] in CRITICAL
            and x.get('http_status') in (404,410)]
    verification='EVIDENCE_HOLD' if broken else (
        'UNAVAILABLE' if home.get('status') not in ('PASS','PARTIAL_PASS') else 'NEEDS_FOUNDER_REVIEW'
    )
    return {
        'domain':domain,
        'observed_epoch':stamp,
        'observed_at':datetime.fromtimestamp(stamp,tz=timezone.utc).isoformat(),
        'home':home_state,
        'checked_links':checks,
        'observed_keyword_topics':{key:sorted(set(urls)) for key,urls in source_topic_urls.items() if urls},
        'keyword_topics_are_verified_terms':False,
        'critical_broken_links':broken,
        'critical_link_status':'BROKEN' if broken else 'NO_BROKEN_CRITICAL_LINK_OBSERVED',
        'state':verification,
        'programme_currently_accepting_verified':False,
        'person_bound_contact_verified':False,
        'payout_economics_contract_verified':False,
        'source_compliance_contract_verified':False,
        'terms_and_data_use_approved':False,
        'integration_verified':False,
        'outbound_authorized':False,
        'execution_authority':'none',
    }


def verified_observation_holds(payload: Mapping[str,Any], *,
                               now_epoch:float) -> dict[str,dict[str,Any]]:
    """Fail-closed validation: reject forged, stale or ambiguous hold reports."""
    if (not isinstance(payload,Mapping)
        or payload.get('schema_version')!='empire.buyer_due_diligence.v1'
        or payload.get('mode')!='OBSERVE'
        or payload.get('execution_authority')!='none'
        or payload.get('outbound_sent') is not False
        or not isinstance(payload.get('observations'),list)
        or len(payload['observations'])>MAX_HISTORY_DOMAINS):
        raise DueDiligenceError('due_diligence_report_invalid')
    result={}
    for row in payload['observations']:
        if not isinstance(row,dict) or not accepted_domain(str(row.get('domain') or '')):
            raise DueDiligenceError('due_diligence_observation_invalid')
        domain=row['domain']
        try:
            observed=float(row['observed_epoch'])
        except (ValueError,TypeError,KeyError) as exc:
            raise DueDiligenceError('due_diligence_timestamp_invalid') from exc
        if observed>now_epoch+120 or observed<=0:
            raise DueDiligenceError('due_diligence_timestamp_out_of_range')
        if row.get('outbound_authorized') is not False:
            raise DueDiligenceError('due_diligence_authority_invalid')
        problems=row.get('critical_broken_links')
        if not isinstance(problems,list) or len(problems)>MAX_LINKS:
            raise DueDiligenceError('due_diligence_critical_links_invalid')
        for problem in problems:
            if (not isinstance(problem,dict)
                or problem.get('category') not in CRITICAL
                or problem.get('http_status') not in (404,410)
                or safe_page_url(domain,str(problem.get('url') or ''))!=problem.get('url')):
                raise DueDiligenceError('due_diligence_broken_link_invalid')
        if problems:
            checked=row.get('checked_links')
            if not isinstance(checked,list):
                raise DueDiligenceError('due_diligence_checked_links_invalid')
            # Requiring recorded page checks means a bare untrusted hold flag
            # cannot be mistaken for actual independent public-page evidence.
            proofs={(x.get('category'),x.get('url'),x.get('http_status'))
                    for x in checked if isinstance(x,dict)}
            if any((x['category'],x['url'],x['http_status']) not in proofs for x in problems):
                raise DueDiligenceError('due_diligence_broken_link_proof_missing')
            if row.get('state')!='EVIDENCE_HOLD':
                raise DueDiligenceError('due_diligence_hold_state_mismatch')
            result[domain]={
                'reason_code':'FIRST_PARTY_CRITICAL_LINK_HTTP_404_OR_410',
                'observed_at':row.get('observed_at'),
                'broken_links':problems,
                'stale':now_epoch-observed>PROMOTION_EVIDENCE_MAX_AGE,
                'review_required':True,
            }
    return result


def load_due_diligence(path: Path, *, now_epoch: float) -> tuple[dict[str,dict[str,Any]],dict[str,dict[str,Any]]]:
    """Load validated due-diligence snapshot; missing means no one is verified."""
    if not path.exists():
        return {},{}
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise DueDiligenceError('due_diligence_artifact_unsafe')
    try:
        payload=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,UnicodeError,ValueError) as exc:
        raise DueDiligenceError('due_diligence_artifact_invalid') from exc
    holds=verified_observation_holds(payload,now_epoch=now_epoch)
    rows={}
    for row in payload['observations']:
        domain=row['domain']
        if domain in rows:
            raise DueDiligenceError('due_diligence_domain_duplicate')
        observed=float(row['observed_epoch'])
        home=row.get('home')
        if not isinstance(home,dict) or home.get('status') not in (
            'PASS','PARTIAL_PASS','HTTP_ERROR','UNAVAILABLE','NOT_PUBLIC','UNSAFE_REDIRECT','UNSUPPORTED_TYPE','PAGE_TOO_LARGE'):
            raise DueDiligenceError('due_diligence_home_status_invalid')
        if home.get('status') in ('PASS','PARTIAL_PASS') and row.get('state') not in ('EVIDENCE_HOLD','NEEDS_FOUNDER_REVIEW'):
            raise DueDiligenceError('due_diligence_state_invalid')
        if row.get('state')=='EVIDENCE_HOLD' and domain not in holds:
            raise DueDiligenceError('due_diligence_missing_hold_proof')
        freshness='CURRENT' if 0<=now_epoch-observed<=PROMOTION_EVIDENCE_MAX_AGE else 'STALE'
        rows[domain]={
            'state':row.get('state'),
            'observed_at':row.get('observed_at'),
            'freshness':freshness,
            'homepage_reachable':home.get('status') in ('PASS','PARTIAL_PASS'),
            'source_capture_partial':home.get('capture_truncated') is True,
            'link_count':len(row.get('checked_links') or []),
            'broken_critical_links':len(row.get('critical_broken_links') or []),
        }
    return rows,holds
