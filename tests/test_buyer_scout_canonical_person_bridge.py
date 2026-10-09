"""Stateful, in-memory contract tests. No runtime gateway or external I/O."""
from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import fnmatch

import pytest

from empire_os.buyer_scout_canonical_person_bridge import materialize_buyer_scout_identity

PID = '10000000-0000-0000-0000-000000000001'
EID = '20000000-0000-0000-0000-000000000001'


def person(name='Adam Hicks', title='Founder & CEO', email='adam@build.example'):
    return dict(name=name, title=title, email=email, source='first_party_site',
                source_url='https://build.example/team', mx_verified=True, mx_confidence=0.75,
                person_explicitly_named=True, email_directly_bound_to_person=True)


class Store:
    def __init__(self, people=None):
        self.calls = []
        self.tables = {name: [] for name in (
            'prospects', 'prospect_acquisitions', 'business_entities', 'prospect_entity_links',
            'intelligence_sources', 'intelligence_people', 'intelligence_employment',
            'intelligence_contact_points', 'intelligence_facts',
        )}
        self.tables['prospects'] = [dict(id=PID, business_name='CooperBuild', website='https://build.example',
            contact_name=None, contact_title=None, contact_source=None, contacted_status='not_contacted')]
        self.tables['prospect_acquisitions'] = [dict(id=str(uuid4()), prospect_id=PID,
            source='buyer_scout_review_ready', ingest_key='buyer_scout_candidate:fixture',
            created_at='2026-09-28T12:00:00+00:00', evidence=dict(domain='build.example',
                source_url='https://build.example', site_evidence=dict(first_party_people=people if people is not None else [person()]))) ]

    @contextmanager
    def transaction(self, request=None):
        before = deepcopy(self.tables)
        try:
            yield request or self
        except BaseException:
            self.tables = before
            raise

    @property
    def people(self):
        return self.tables['prospect_acquisitions'][0]['evidence']['site_evidence']['first_party_people']

    @property
    def writes(self):
        return [call for call in self.calls if call[0] != 'GET']

    def __call__(self, method, path, payload=None, prefer=None):
        parsed = urlsplit(path)
        table = parsed.path.split('/')[-1]
        assert table in self.tables, f'Forbidden table: {table}'
        params = {k:v[0] for k,v in parse_qs(parsed.query).items()}
        self.calls.append((method, table, deepcopy(payload), params))
        def matches(row):
            for key, condition in params.items():
                if key in ('select','order','limit','offset','on_conflict'):
                    continue
                value = row.get(key)
                if condition == 'is.null':
                    if value is not None: return False
                elif condition == 'not.is.null':
                    if value is None: return False
                elif condition.startswith('eq.'):
                    if str(value).lower() != condition[3:].lower(): return False
                elif condition.startswith('in.('):
                    if str(value) not in condition[4:-1].split(','): return False
                elif condition.startswith('ilike.'):
                    if not fnmatch.fnmatch(str(value).lower(), condition[6:].lower()): return False
                else:
                    raise AssertionError(condition)
            return True
        rows = [row for row in self.tables[table] if matches(row)]
        if method == 'GET':
            if params.get('order'):
                for ordering in reversed(params['order'].split(',')):
                    key,direction = ordering.split('.')[:2]
                    rows.sort(key=lambda row: str(row.get(key) or ''), reverse=direction=='desc')
            return deepcopy(rows[:int(params.get('limit', 1000))])
        if method == 'POST':
            conflict = params.get('on_conflict')
            if not conflict and 'ignore-duplicates' in (prefer or ''):
                unique_keys = ['id']
                if table == 'intelligence_facts':
                    unique_keys.append('evidence_hash')
                if any(payload.get(key) is not None and row.get(key) == payload[key]
                       for key in unique_keys for row in self.tables[table]):
                    return []
            if conflict:
                existing = [row for row in self.tables[table] if row.get(conflict)==payload.get(conflict)]
                if existing:
                    if 'merge-duplicates' in (prefer or ''):
                        existing[0].update(payload)
                        return deepcopy(existing)
                    return []
            row = {'id': str(uuid4()), **deepcopy(payload)}
            self.tables[table].append(row)
            return [deepcopy(row)]
        if method == 'PATCH':
            for row in rows:
                row.update(deepcopy(payload))
            return deepcopy(rows)
        raise AssertionError(method)


def run(store, write=True, pid=PID):
    return materialize_buyer_scout_identity(prospect_id=pid, write_authorized=write, request_factory=store, transaction_factory=store.transaction)


def link(store, eid=EID):
    store.tables['business_entities'].append(dict(id=eid, canonical_website='https://build.example'))
    store.tables['prospect_entity_links'].append(dict(id=str(uuid4()), prospect_id=PID, entity_id=eid, active=True))


def test_verified_person_canonicalizes_and_projects_without_external_state():
    db = Store()
    result = run(db)
    assert result['ok'], result
    assert result['projection_performed']
    p = db.tables['intelligence_people'][0]
    employment = db.tables['intelligence_employment'][0]
    contact = db.tables['intelligence_contact_points'][0]
    assert employment['person_id'] == contact['person_id'] == p['id']
    assert employment['entity_id'] == contact['entity_id'] == result['entity_id']
    assert employment['title'] == 'Founder & CEO'
    assert employment['normalized_title'] == 'founder ceo'
    assert employment['is_current'] is True
    assert all(employment[k] is None for k in ('seniority','department','buying_role'))
    assert employment['confidence'] == contact['confidence'] == p['identity_confidence'] == .75
    assert contact['contact_type'] == 'work_email'
    assert contact['verification_state'] == 'verified'
    assert contact['value'] == contact['normalized_value'] == 'adam@build.example'
    assert db.tables['intelligence_facts'][0]['fact_value']['mx_verified'] is True
    assert db.tables['intelligence_facts'][0]['evidence_uri'] == 'https://build.example/team'
    prospect = db.tables['prospects'][0]
    assert prospect['contact_name'] == 'Adam Hicks'
    assert prospect['contacted_status'] == 'not_contacted'
    assert all('contacted_status' not in (payload or {}) for _,_,payload,_ in db.writes)
    assert not any(result[key] for key in ('outbound_actions','payment_actions','revenue_actions','external_execution_performed'))


def test_observe_zero_writes():
    db = Store()
    result = run(db, False)
    assert result['ok'] and result['mode'] == 'OBSERVE'
    assert db.writes == []
    assert result['materializer']['mode'] == 'OBSERVE'


@pytest.mark.parametrize('field,value', [('email_directly_bound_to_person',False), ('mx_verified',False),
    ('person_explicitly_named',False), ('name',''), ('title',''), ('email',''), ('source','third_party'),
    ('source_url',''), ('mx_confidence',None), ('mx_confidence',float('nan'))])
def test_ineligible_contact_has_no_mutation(field, value):
    db=Store(); db.people[0][field]=value
    assert run(db)['status'] == 'NO_VERIFIED_FIRST_PARTY_PERSON'
    assert not db.writes


def test_existing_link_reused():
    db=Store(); link(db)
    assert run(db)['entity_id']==EID
    assert not [c for c in db.writes if c[1] in ('business_entities','prospect_entity_links')]


def test_ambiguous_entities_fail_closed():
    db=Store()
    db.tables['business_entities']=[dict(id=str(uuid4()),canonical_website=url) for url in
                                   ('https://build.example', 'http://www.build.example/team')]
    assert run(db)['status']=='AMBIGUOUS_BUSINESS_ENTITY'
    assert not db.writes


def test_exact_domain_dominates_name():
    db=Store()
    db.tables['business_entities']=[dict(id=EID,canonical_website='http://www.build.example/team',canonical_name='Different Name'),
                                   dict(id=str(uuid4()),canonical_website='https://unrelated.example',canonical_name='CooperBuild')]
    assert run(db)['entity_id']==EID
    assert len(db.tables['business_entities'])==2


def test_idempotent_rerun_preserves_stronger_contact():
    db=Store(); assert run(db)['ok']
    counts={k:len(v) for k,v in db.tables.items()}
    contact=db.tables['intelligence_contact_points'][0]
    contact.update(confidence=.96, verified_at='2026-09-20T00:00:00+00:00')
    assert run(db)['ok']
    assert counts=={k:len(v) for k,v in db.tables.items()}
    assert contact['confidence']==.96
    assert contact['verified_at']=='2026-09-20T00:00:00+00:00'


def test_same_name_other_entity_is_distinct():
    db=Store(); run(db)
    first_person=db.tables['intelligence_people'][0]['id']
    other_pid=str(uuid4())
    db.tables['prospects'].append(dict(id=other_pid,business_name='Other',website='https://other.example'))
    acquisition=deepcopy(db.tables['prospect_acquisitions'][0]); acquisition.update(id=str(uuid4()),prospect_id=other_pid)
    acquisition['evidence'].update(domain='other.example',source_url='https://other.example')
    acquisition['evidence']['site_evidence']['first_party_people'][0].update(email='adam@other.example',source_url='https://other.example/team')
    db.tables['prospect_acquisitions'].append(acquisition)
    assert run(db,pid=other_pid)['ok']
    assert len(db.tables['intelligence_people'])==2
    assert db.tables['intelligence_people'][1]['id']!=first_person


def test_tied_managing_directors_canonicalize_without_projection():
    people=[person('Chris Welch','Managing Director','chris@build.example'), person('Aaron Davis','Managing Director','aaron@build.example')]
    results=[]
    for rows in (people, list(reversed(people))):
        db=Store(rows); result=run(db); results.append(result['decision_candidates'])
        assert result['ok'] and result['decision_status']=='AMBIGUOUS_DECISION_MAKER'
        assert len(db.tables['intelligence_people'])==2
        assert not result['projection_performed']
        assert db.tables['prospects'][0]['contact_name'] is None
    assert results[0]==results[1]


def test_unique_economic_buyer_dominates_non_economic_title():
    db=Store([person(),person('Other Person','Vice President','other@build.example')])
    assert run(db)['decision_maker']['name']=='Adam Hicks'
    assert len(db.tables['intelligence_people'])==2


def test_existing_projection_preserved():
    db=Store(); db.tables['prospects'][0].update(contact_name='Existing Person',contact_title='CEO',contact_source='stronger_evidence')
    result=run(db)
    assert result['projection_status']=='EXISTING_PROJECTION_PRESERVED'
    assert not result['review_input']['review_ready']
    assert result['review_input']['rejection_reason']=='EXISTING_DECISION_MAKER_CONFLICT'
    assert db.tables['prospects'][0]['contact_name']=='Existing Person'


def test_ambiguous_current_people_fail_closed():
    db=Store(); link(db)
    for _ in range(2):
        person_id=str(uuid4())
        db.tables['intelligence_people'].append(dict(id=person_id,normalized_name='adam hicks'))
        db.tables['intelligence_employment'].append(dict(id=str(uuid4()),person_id=person_id,entity_id=EID,is_current=True))
    result=run(db)
    assert not result['ok'] and result['retryable']
    assert not db.tables['intelligence_contact_points']


@pytest.mark.parametrize('active', [False,None])
def test_inactive_link_not_reactivated(active):
    db=Store(); link(db); db.tables['prospect_entity_links'][0]['active']=active
    assert run(db)['status']=='AMBIGUOUS_PROSPECT_ENTITY_LINK'
    assert not db.writes


def test_shared_email_for_different_people_rejected():
    db=Store([person(),person('Other Person')])
    assert run(db)['status']=='AMBIGUOUS_ACQUISITION_EMAIL'
    assert not db.writes


def test_person_insertion_rolls_back_and_retry_does_not_duplicate():
    db=Store()
    failed=False
    def flaky(method,path,**kwargs):
        nonlocal failed
        if method=='POST' and '/intelligence_employment' in path and not failed:
            failed=True
            raise RuntimeError('injected employment failure')
        return db(method,path,**kwargs)
    first=materialize_buyer_scout_identity(prospect_id=PID,write_authorized=True,request_factory=flaky, transaction_factory=lambda: db.transaction(flaky))
    assert not first['ok'] and first['retryable']
    assert len(db.tables['intelligence_people'])==0
    assert first['transaction_state'] == 'rolled_back'
    assert first['internal_mutation_performed'] is False
    assert run(db)['ok']
    assert len(db.tables['intelligence_people'])==1
    assert len(db.tables['intelligence_employment'])==1


def test_hunter_will_not_rebind_contact_or_regress_observation():
    db=Store(); assert run(db)['ok']
    contact=db.tables['intelligence_contact_points'][0]
    contact['last_seen_at']='2026-10-01T00:00:00+00:00'
    assert run(db)['ok']
    assert contact['last_seen_at']=='2026-10-01T00:00:00+00:00'
    contact['person_id']=str(uuid4())
    saved=deepcopy(contact)
    assert not run(db)['ok']
    assert contact==saved


@pytest.mark.parametrize('state',['suppressed','invalid'])
def test_stronger_negative_contact_evidence_blocks_review_and_projection(state):
    db=Store(); run(db)
    db.tables['intelligence_contact_points'][0]['verification_state']=state
    db.tables['prospects'][0].update(contact_name=None,contact_title=None,contact_source=None)
    result=run(db)
    assert not result['ok'] and result['blocker']=='CANONICAL_CONTACT_CONFLICT'
    assert not result['review_input']['review_ready']
    assert not result['projection_performed']
    assert db.tables['intelligence_contact_points'][0]['verification_state']==state


def test_review_input_uses_existing_materializer_without_crawl():
    from empire_os.buyer_review_materializer import run_buyer_review_materializer
    db=Store()
    db.tables['buyer_candidate_reviews']=[]
    db.tables['prospects'][0].update(niche='permit_intelligence', buy_signal_score=90,
                                   phone='+15555550123', metro='New York', address='1 Example St')
    bridge=run(db)
    assert bridge['review_input']['review_ready']
    assert bridge['review_input']['person_bound']
    proposals=[]
    def request(method,path,payload=None,**kwargs):
        if method=='POST' and path=='/rest/v1/rpc/propose_buyer_candidate_review':
            proposals.append(payload)
            return {'decision':'proposed','review_id':str(uuid4())}
        return db(method,path,payload=payload,**kwargs)
    result=run_buyer_review_materializer(request=request,probe=lambda row:bridge['review_input'],
        prospect_ids=[PID],scan_limit=1,proposal_limit=1,probe_workers=1)
    assert result.proposed==1, result.as_dict()
    assert proposals[0]['p_prospect_id']==PID
    assert proposals[0]['p_entity_id']==bridge['entity_id']
    assert proposals[0]['p_evidence']['person_bound'] is True
    assert proposals[0]['p_evidence']['verified_contacts'][0]['confidence']==.75


def test_latest_scout_acquisition_not_another_source_or_prospect():
    db=Store()
    stale=deepcopy(db.tables['prospect_acquisitions'][0]); stale.update(id=str(uuid4()),created_at='2026-08-01T00:00:00+00:00')
    stale['evidence']['site_evidence']['first_party_people']=[person('Stale Person')]
    unrelated=deepcopy(stale); unrelated.update(id=str(uuid4()),source='other',created_at='2026-10-01T00:00:00+00:00')
    db.tables['prospect_acquisitions'] += [stale,unrelated]
    assert run(db)['decision_maker']['name']=='Adam Hicks'


def test_link_conflict_during_insert_is_not_overwritten():
    db=Store()
    other=str(uuid4())
    def raced(method,path,payload=None,**kwargs):
        if method=='POST' and '/prospect_entity_links?' in path:
            db.tables['prospect_entity_links'].append(dict(prospect_id=PID,entity_id=other,active=True))
        return db(method,path,payload=payload,**kwargs)
    result=materialize_buyer_scout_identity(prospect_id=PID,write_authorized=True,request_factory=raced, transaction_factory=lambda: db.transaction(raced))
    assert result['status']=='PROSPECT_ENTITY_LINK_CONFLICT'
    assert db.tables['prospect_entity_links'] == []
    assert not db.tables['intelligence_people']


def test_domain_conflict_has_no_mutation():
    db=Store(); db.people[0]['source_url']='https://different.example/team'
    assert run(db)['status']=='PERSON_SOURCE_DOMAIN_CONFLICT'
    assert not db.writes


def test_ambiguous_people_fail_before_any_hunter_writes():
    db=Store(); link(db)
    for _ in range(2):
        person_id=str(uuid4())
        db.tables['intelligence_people'].append(dict(id=person_id,normalized_name='adam hicks'))
        db.tables['intelligence_employment'].append(dict(id=str(uuid4()),person_id=person_id,entity_id=EID,is_current=True))
    result=run(db)
    assert not result['ok']
    assert not result['internal_mutation_performed']
    assert not db.writes


def test_historical_same_name_is_not_treated_as_an_orphan_retry():
    db=Store(); run(db)
    db.tables['intelligence_employment'][0]['is_current']=False
    result=run(db)
    assert not result['ok']
    assert not any(e['is_current'] for e in db.tables['intelligence_employment'])


def test_observe_rejects_truthy_non_boolean_authority():
    db=Store(); result=run(db,'false')
    assert result['mode']=='OBSERVE'
    assert not db.writes


@pytest.mark.parametrize('write', [False, True])
@pytest.mark.parametrize('concurrent', [None, 'contact_name', 'contact_title', 'contact_source'])
def test_cooperbuild_real_compatibility_boundary(monkeypatch, write, concurrent):
    from urllib.parse import urlencode
    import empire_os.sb as sb

    db = Store()
    prospect = db.tables['prospects'][0]
    prospect.update(contact_source='buyer_scout_review_ready', website='https://cooperbuild.com/')
    evidence = db.tables['prospect_acquisitions'][0]['evidence']
    evidence.update(domain='cooperbuild.com', source_url='https://cooperbuild.com/')
    db.people[0].update(email='adam@cooperbuild.com',
                       source_url='https://cooperbuild.com/about/who-we-are/')

    class Gateway:
        configured = True

        def query(self, table, columns, **kwargs):
            # The actual facade has already validated every column/filter.
            assert columns != '*' and '*' not in columns
            rows = db('GET', current_path[0])
            return [{key: row.get(key) for key in columns.split(',')} for row in rows]

        def insert_ignore_conflicts(self, table, row, **kwargs):
            return db('POST', current_path[0], payload=row,
                      prefer='resolution=ignore-duplicates,return=representation')

        def upsert(self, table, row, **kwargs):
            return db('POST', current_path[0], payload=row,
                      prefer='resolution=merge-duplicates,return=representation')

        def insert(self, table, row, **kwargs):
            return db('POST', current_path[0], payload=row)

        def update(self, table, match, values):
            assert match
            if table == 'prospects' and concurrent:
                prospect[concurrent] = 'Concurrent projection'
            params = {key: 'is.null' if value is None else f'eq.{value}'
                      for key, value in match.items()}
            return db('PATCH', f'/rest/v1/{table}?{urlencode(params)}', payload=values)

    current_path = [None]
    monkeypatch.setattr(sb, '_runtime_gateway', lambda: Gateway())

    def request(method, path, **kwargs):
        current_path[0] = path
        return sb.request_json(method, path, **kwargs)

    @contextmanager
    def transaction():
        try:
            with db.transaction(request) as scoped:
                yield scoped
        except BaseException:
            # Model the competing commit as external to our rolled-back unit.
            if concurrent:
                db.tables['prospects'][0][concurrent] = 'Concurrent projection'
            raise

    result = materialize_buyer_scout_identity(
        prospect_id=PID, write_authorized=write, request_factory=request, transaction_factory=transaction)
    assert result['ok'] == (not write or not concurrent), result
    assert result['decision_maker']['name'] == 'Adam Hicks'
    assert result.get('projection_status') != 'EXISTING_PROJECTION_PRESERVED'
    assert prospect['contacted_status'] == 'not_contacted'
    if not write:
        assert db.writes == []
    elif concurrent:
        assert result['projection_status'] == 'CONCURRENT_PROJECTION_PRESERVED'
        assert db.tables['prospects'][0][concurrent] == 'Concurrent projection'
        assert result['transaction_state'] == 'rolled_back'
        assert not result['review_input']['review_ready']
        assert not db.tables['intelligence_people']
    else:
        assert result['projection_status'] == 'PROJECTED'
        assert prospect['contact_name'] == 'Adam Hicks'
        assert prospect['contact_title'] == 'Founder & CEO'


def test_bridge_has_no_wildcard_projection():
    import ast
    import inspect
    import empire_os.buyer_scout_canonical_person_bridge as bridge

    tree = ast.parse(inspect.getsource(bridge))
    selects = [kw.value for node in ast.walk(tree) if isinstance(node, ast.Call)
               for kw in node.keywords if kw.arg == 'select']
    assert selects
    assert all(isinstance(value, ast.Constant) and '*' not in value.value for value in selects)


@pytest.mark.parametrize("stage", [
    "business_entities", "prospect_entity_links", "intelligence_sources",
    "intelligence_people", "intelligence_employment", "intelligence_contact_points",
    "intelligence_facts", "prospects",
])
def test_every_major_write_rolls_back_entire_unit(stage):
    db = Store()
    before = deepcopy(db.tables)
    def fail_after_write(method, path, **kwargs):
        rows = db(method, path, **kwargs)
        if method != "GET" and urlsplit(path).path.rsplit("/", 1)[-1] == stage:
            raise RuntimeError("sensitive response must never escape")
        return rows
    result = materialize_buyer_scout_identity(
        prospect_id=PID, write_authorized=True,
        transaction_factory=lambda: db.transaction(fail_after_write))
    assert not result["ok"]
    assert result["failure_stage"] == stage
    assert result["transaction_state"] == "rolled_back"
    assert result["internal_write_attempted"]
    assert not result["internal_mutation_performed"]
    assert not result["write_outcome_unknown"]
    assert "sensitive response" not in str(result)
    assert db.tables == before


def test_cooperbuild_partial_state_completes_without_cleanup():
    db = Store()
    assert run(db)["ok"]
    db.tables["intelligence_facts"] = []
    db.tables["prospects"][0].update(contact_name=None, contact_title=None,
                                    contact_source="buyer_scout_review_ready")
    ids = {table: [row["id"] for row in rows] for table, rows in db.tables.items()}
    assert run(db)["ok"]
    assert len(db.tables["intelligence_facts"]) == 1
    for table, previous in ids.items():
        if table != "intelligence_facts":
            assert [row["id"] for row in db.tables[table]] == previous
    assert db.tables["prospects"][0]["contact_name"] == "Adam Hicks"


@pytest.mark.parametrize("conflict", ["entity", "link", "person", "fact", "suppressed", "binding"])
def test_conflicting_partial_state_unchanged(conflict):
    db = Store()
    assert run(db)["ok"]
    db.tables["prospects"][0].update(contact_name=None, contact_title=None)
    if conflict == "entity":
        db.tables["business_entities"][0]["canonical_website"] = "https://wrong.example"
    elif conflict == "link":
        db.tables["prospect_entity_links"][0]["entity_id"] = str(uuid4())
    elif conflict == "person":
        db.tables["intelligence_people"][0]["normalized_name"] = "someone else"
        db.tables["intelligence_employment"] = []
    elif conflict == "fact":
        db.tables["intelligence_facts"][0]["fact_value"] = {"conflicting": True}
    elif conflict == "suppressed":
        db.tables["intelligence_contact_points"][0]["verification_state"] = "suppressed"
    else:
        db.tables["intelligence_contact_points"][0]["person_id"] = str(uuid4())
    before = deepcopy(db.tables)
    result = run(db)
    assert not result["ok"]
    assert db.tables == before


def test_ambiguous_decision_still_requires_all_verified_contacts():
    db = Store([person("Chris Welch", "Managing Director", "chris@build.example"),
                person("Aaron Davis", "Managing Director", "aaron@build.example")])
    assert run(db)["ok"]
    db.tables["intelligence_contact_points"][0]["verification_state"] = "suppressed"
    before = deepcopy(db.tables)
    assert run(db)["blocker"] == "CANONICAL_CONTACT_CONFLICT"
    assert db.tables == before


def test_live_custom_request_cannot_silently_bypass_transaction():
    db = Store()
    result = materialize_buyer_scout_identity(prospect_id=PID, write_authorized=True,
                                              request_factory=db)
    assert result["blocker"] == "ATOMIC_TRANSACTION_REQUIRED"
    assert not db.calls


def test_observe_never_opens_transaction():
    db = Store()
    def forbidden():
        raise AssertionError("OBSERVE opened a transaction")
    result = materialize_buyer_scout_identity(prospect_id=PID, write_authorized=False,
                                              request_factory=db, transaction_factory=forbidden)
    assert result["ok"] and not db.writes


def test_live_revalidates_acquisition_inside_transaction():
    db = Store()
    @contextmanager
    def transaction():
        db.people[0]["mx_verified"] = False
        with db.transaction() as request:
            yield request
    result = materialize_buyer_scout_identity(prospect_id=PID, write_authorized=True,
                                              request_factory=db, transaction_factory=transaction)
    assert result["blocker"] == "NO_VERIFIED_FIRST_PARTY_PERSON"
    assert not db.writes


def test_conflicting_deterministic_person_cannot_hide_behind_current_match():
    from uuid import UUID, uuid5
    db = Store()
    assert run(db)["ok"]
    eid = db.tables["business_entities"][0]["id"]
    stable_id = str(uuid5(UUID(eid), "adam hicks"))
    alternate_id = str(uuid4())
    db.tables["intelligence_people"][0]["id"] = alternate_id
    db.tables["intelligence_employment"][0]["person_id"] = alternate_id
    db.tables["intelligence_people"].append(dict(id=stable_id, normalized_name="someone else"))
    before = deepcopy(db.tables)
    assert not run(db)["ok"]
    assert db.tables == before


def test_later_failure_restores_employment_change_and_contact_refresh():
    db = Store()
    assert run(db)["ok"]
    db.tables["intelligence_employment"][0].update(title="Director", normalized_title="director")
    db.tables["intelligence_contact_points"][0].update(confidence=.40, verification_state="observed")
    # Force a new fact insert after the employment and contact changes.
    db.tables["intelligence_facts"] = []
    before = deepcopy(db.tables)
    def fail_fact(method, path, **kwargs):
        result = db(method, path, **kwargs)
        if method == "POST" and urlsplit(path).path == "/rest/v1/intelligence_facts":
            raise RuntimeError("after employment retirement and contact refresh")
        return result
    result = materialize_buyer_scout_identity(prospect_id=PID, write_authorized=True,
        transaction_factory=lambda: db.transaction(fail_fact))
    assert not result["ok"] and db.tables == before
    assert run(db)["ok"]
    employment = db.tables["intelligence_employment"]
    assert len(employment) == 2
    assert employment[0]["is_current"] is False
    assert employment[1]["is_current"] is True
